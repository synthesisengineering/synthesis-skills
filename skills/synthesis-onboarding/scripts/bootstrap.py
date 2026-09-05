#!/usr/bin/env python3
"""Materialize and activate one verified immutable synthesis release."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from system_contract import (
    ContractError,
    activate_cli,
    validate_release_descriptor,
    release_descriptor_from_checkout,
    verify_materialized_release,
)


def _tracked_files(source: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(source), "ls-files", "-z"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        raise ContractError(
            "could not enumerate tracked release files: %s"
            % completed.stderr.decode("utf-8", errors="replace").strip()
        )
    files = [item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]
    if not files:
        raise ContractError("release has no tracked files")
    return sorted(files)


def _copy_regular_tree(source: Path, destination: Path) -> None:
    """Copy exactly the Git-tracked release tree, excluding test/build residue."""
    source = source.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    verified_directories = {source}
    for relative_text in _tracked_files(source):
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise ContractError("tracked release path is unsafe: %s" % relative_text)
        source_path = source / relative
        current = source
        for part in relative.parts[:-1]:
            current = current / part
            if current not in verified_directories:
                metadata = current.lstat()
                if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                    raise ContractError(
                        "release tree contains a link or special directory: %s"
                        % current.relative_to(source)
                    )
                verified_directories.add(current)
        metadata = source_path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ContractError("release tree contains a link or special file: %s" % relative)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
        os.chmod(target, 0o755 if metadata.st_mode & stat.S_IXUSR else 0o644)


def _make_read_only(root: Path) -> None:
    files = []
    directories = []
    for directory, dirnames, filenames in os.walk(root):
        current = Path(directory)
        directories.append(current)
        files.extend(current / name for name in filenames)
        directories.extend(current / name for name in dirnames)
    for path in files:
        mode = 0o555 if path.stat().st_mode & stat.S_IXUSR else 0o444
        os.chmod(path, mode)
    for path in sorted(set(directories), key=lambda item: len(item.parts), reverse=True):
        os.chmod(path, 0o555)


def _verify_read_only(root: Path) -> None:
    for directory, dirnames, filenames in os.walk(root):
        current = Path(directory)
        for path in [current, *(current / name for name in dirnames), *(current / name for name in filenames)]:
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise ContractError("immutable generation contains a symbolic link")
            if metadata.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
                raise ContractError("immutable generation remains writable: %s" % path)


def materialize_release(
    checkout: Path,
    releases_dir: Path,
    *,
    channel: str,
    ref: str,
    source_url: str,
) -> tuple[Path, dict]:
    descriptor = release_descriptor_from_checkout(
        checkout,
        channel=channel,
        ref=ref,
        source_url=source_url,
    )
    releases_dir = Path(releases_dir)
    releases_dir.mkdir(parents=True, exist_ok=True)
    generation = releases_dir / descriptor["content_digest"]
    if generation.exists():
        if not generation.is_dir() or generation.is_symlink():
            raise ContractError("immutable generation path is not a real directory")
        verify_materialized_release(generation, descriptor)
        _make_read_only(generation)
        _verify_read_only(generation)
        return generation, descriptor
    staging = Path(tempfile.mkdtemp(prefix=".release-stage-", dir=releases_dir))
    try:
        staging.rmdir()
        _copy_regular_tree(Path(checkout), staging)
        verify_materialized_release(staging, descriptor)
        try:
            os.replace(staging, generation)
        except OSError:
            if not generation.is_dir():
                raise
            verify_materialized_release(generation, descriptor)
            shutil.rmtree(staging)
        _make_read_only(generation)
        _verify_read_only(generation)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return generation, descriptor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--releases-dir", required=True, type=Path)
    parser.add_argument("--launcher", required=True, type=Path)
    parser.add_argument("--active-descriptor", required=True, type=Path)
    parser.add_argument("--channel", required=True, choices=["stable", "edge", "pin"])
    parser.add_argument("--ref", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("cli_args", nargs=argparse.REMAINDER)
    return parser


def _validate_cli_arguments(checkout: Path, cli_args: list[str]) -> None:
    """Refuse an invalid command line before any generation is activated.

    The public CLI that ships inside the checkout owns the argument
    contract, so its parser is loaded from that checkout and asked to parse
    the arguments; activation never happens for a command the CLI would
    reject afterwards.
    """
    cli_path = Path(checkout) / "skills" / "synthesis-onboarding" / "scripts" / "synthesis_cli.py"
    if cli_path.is_symlink() or not cli_path.is_file():
        raise ContractError("release has no trusted synthesis CLI")
    scripts_dir = str(cli_path.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("synthesis_release_cli", cli_path)
    if spec is None or spec.loader is None:
        raise ContractError("release CLI could not be loaded for argument validation")
    module = importlib.util.module_from_spec(spec)
    # Loading the parser must not write bytecode into the checkout: a release
    # checkout has to stay clean for its descriptor to be derived.
    previous_bytecode_policy = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    except SystemExit as exc:
        raise ContractError("release CLI exited during argument validation (%s)" % exc.code) from exc
    finally:
        sys.dont_write_bytecode = previous_bytecode_policy
    build = getattr(module, "build_parser", None)
    if not callable(build):
        raise ContractError("release CLI has no argument parser")
    try:
        build().parse_args(cli_args or ["setup"])
    except SystemExit as exc:
        raise ContractError(
            "invalid command line %r (parser exit %s)" % (cli_args, exc.code)
        ) from exc


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cli_args = list(args.cli_args)
    if cli_args[:1] == ["--"]:
        cli_args = cli_args[1:]
    try:
        _validate_cli_arguments(args.checkout, cli_args)
    except ContractError as exc:
        print("Synthesis bootstrap refused: %s" % exc, file=sys.stderr)
        return 2
    try:
        generation, descriptor = materialize_release(
            args.checkout,
            args.releases_dir,
            channel=args.channel,
            ref=args.ref,
            source_url=args.source_url,
        )
        active_path = Path(args.active_descriptor)
        if args.channel != "pin" and active_path.is_file() and not active_path.is_symlink():
            try:
                current = json.loads(active_path.read_text(encoding="utf-8"))
                current_descriptor = validate_release_descriptor(
                    {key: current.get(key) for key in (
                        "schema_version", "version", "channel", "ref", "commit", "tree",
                        "content_digest", "digest_algorithm", "tree_policy", "source_url",
                        "resolved_at",
                    )}
                )
                current_root = Path(current["release_root"])
                if (
                    current_descriptor["channel"] == descriptor["channel"]
                    and current_descriptor["ref"] == descriptor["ref"]
                    and tuple(map(int, current_descriptor["version"].split(".")))
                    > tuple(map(int, descriptor["version"].split(".")))
                ):
                    verify_materialized_release(current_root, current_descriptor)
                    _make_read_only(current_root)
                    _verify_read_only(current_root)
                    generation, descriptor = current_root, current_descriptor
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ContractError("active release pointer is invalid: %s" % exc)
        activate_cli(generation, descriptor, args.launcher, args.active_descriptor)
    except (ContractError, OSError) as exc:
        print("Synthesis bootstrap refused: %s" % exc, file=sys.stderr)
        return 1
    cli = generation / "skills" / "synthesis-onboarding" / "scripts" / "synthesis_cli.py"
    command = [sys.executable, "-B", str(cli)] + (cli_args or ["setup"])
    environment = dict(os.environ)
    environment["SYNTHESIS_ACTIVE_DESCRIPTOR"] = str(args.active_descriptor)
    environment["SYNTHESIS_BOOTSTRAP_RESOLVED"] = "1"
    # The public acquisition stage is HTTPS-only. The now-verified CLI also
    # acquires validated organization repositories over SSH; keep file/ext
    # transports forbidden without leaking the narrower download policy.
    environment["GIT_ALLOW_PROTOCOL"] = "https:ssh"
    environment["GIT_PROTOCOL_FROM_USER"] = "0"
    return subprocess.call(command, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
