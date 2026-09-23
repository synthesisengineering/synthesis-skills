#!/usr/bin/env python3
"""Block edits to generated instructions, adapters, and installed skills."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


HOME = Path.home().resolve()
PROTECTED_ROOTS = (
    HOME / ".claude" / "skills",
    HOME / ".agents" / "skills",
    HOME / ".codex" / "skills",
)
GENERATED_RULES = (
    HOME / "AGENTS.md",
    HOME / ".claude" / "CLAUDE.md",
    HOME / ".codex" / "AGENTS.md",
)


def resolve(value: str, cwd: str) -> Path | None:
    cleaned = os.path.expanduser(value.strip().strip('"').strip("'"))
    if not cleaned:
        return None
    path = Path(cleaned)
    if not path.is_absolute():
        path = Path(cwd or os.getcwd()) / path
    try:
        return path.resolve(strict=False)
    except OSError:
        return None


def patch_paths(text: str) -> list[str]:
    matches = []
    for line in text.splitlines():
        found = re.match(
            r"\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+)$", line
        )
        if found:
            matches.append(found.group(1).strip())
    return matches


def is_complete_patch_envelope(text: str) -> bool:
    """Return true only for one complete, path-bearing patch document."""
    lines = text.strip().splitlines()
    return (
        len(lines) >= 3
        and lines[0] == "*** Begin Patch"
        and lines[-1] == "*** End Patch"
        and lines.count("*** Begin Patch") == 1
        and lines.count("*** End Patch") == 1
        and bool(patch_paths(text))
    )


def positional_arguments(arguments: list[str]) -> list[str]:
    """Return shell operands while preserving numeric and post-``--`` names."""
    values: list[str] = []
    options = True
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token == "--":
            options = False
            index += 1
            continue
        if options and token.startswith("-"):
            index += 1
            continue
        values.append(token)
        index += 1
    return values


def shell_write_paths(command: str, cwd: str, *, depth: int = 0,
                      unknown_cwd: bool = False, unknown_home: bool = False) -> tuple[list[Path], list[str]]:
    """Extract destinations from common shell mutation forms.

    The shared shell parser separates executable input from literal heredoc
    data. This backstop recognizes common write commands; arbitrary interpreter
    programs remain covered by source/install drift checks, not claimed as
    complete interception here.
    """
    paths: list[Path] = []
    errors: list[str] = []
    if depth > 16:
        return [], ["Installed-artifact guard shell nesting exceeds inspection limit"]
    try:
        # PRO-2: the shell parser is a public module since 4.128.0, bound
        # lazily through the verified public runtime; PublicRuntimeError is
        # a ValueError, so a missing runtime keeps this function's existing
        # error-string contract instead of raising.
        import public_runtime
        parser = public_runtime.public_module(
            "synthesis-project-management", "publication_command",
            floor="4.128.0", consumer="installed_artifact_guard")
        syntax = parser.parse_shell(command)
        unwrap_argv = parser.unwrap_argv
    except (ImportError, SyntaxError, ValueError, AttributeError) as exc:
        return [], [f"Installed-artifact guard could not parse shell command: {exc}"]
    mutators_all_args = {"rm", "mkdir", "rmdir", "touch", "tee"}
    mutators_last_arg = {"cp", "mv", "install", "rsync", "ln"}
    initial = resolve(cwd or os.getcwd(), cwd or os.getcwd())
    possible_cwds: set[Path | None] = {None if unknown_cwd or syntax.grouped else initial}
    seen_cwds = set(possible_cwds)
    directory_environment = {"CDPATH"} if os.environ.get("CDPATH") else set()
    if unknown_home:
        directory_environment.add("HOME")

    def add_destination(destination: str, kind: str) -> None:
        if "HOME" in directory_environment and (destination == "~" or destination.startswith("~/")
                                                or any(marker in destination for marker in ("$HOME", "${HOME}"))):
            errors.append(f"Installed-artifact guard cannot resolve a changed HOME in a {kind} destination")
            return
        expanded = destination.replace("${HOME}", str(HOME)).replace("$HOME", str(HOME))
        if syntax.dynamic and any(marker in expanded for marker in ("$", "`")):
            errors.append(f"Installed-artifact guard cannot resolve a dynamic {kind} destination")
            return
        absolute = Path(os.path.expanduser(expanded)).is_absolute()
        for base in possible_cwds:
            if base is None and not absolute:
                errors.append(f"Installed-artifact guard cannot resolve a relative {kind} after a dynamic cd")
                continue
            path = resolve(expanded, str(base or cwd))
            if path is not None:
                paths.append(path)

    for index, words in enumerate(syntax.commands):
        if index and syntax.separators[index - 1] == "||":
            possible_cwds |= seen_cwds
        for word in words:
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word):
                break
            name = word.split("=", 1)[0]
            if name in {"HOME", "CDPATH", "PWD", "OLDPWD"}:
                directory_environment.add(name)
        try:
            argv = unwrap_argv(words)
        except ValueError as exc:
            errors.append(f"Installed-artifact guard could not resolve executable command: {exc}")
            continue
        parent_cwds = set(possible_cwds)
        prefix = words[:len(words) - len(argv)] if argv else []
        child_home_unknown = "HOME" in directory_environment or any(word.startswith("HOME=") for word in prefix)
        wrapped_directory = any(word.split("=", 1)[0] in {"-C", "--chdir", "--cwd", "-D", "--chroot", "-R"}
                                for word in prefix)
        if wrapped_directory:
            possible_cwds = {None}
        for owner, script in syntax.nested_commands:
            if owner != index:
                continue
            for base in possible_cwds:
                nested_paths, nested_errors = shell_write_paths(script, str(base or cwd), depth=depth + 1,
                                                                unknown_cwd=base is None, unknown_home=child_home_unknown)
                paths.extend(nested_paths)
                errors.extend(nested_errors)
        for owner, operator, operand in syntax.redirections:
            if owner == index and ">" in operator:
                if operator.endswith("&") and (operand.isdigit() or operand == "-"):
                    continue
                add_destination(operand, "redirection")
        if not argv:
            continue
        command_name = Path(argv[0]).name
        arguments = argv[1:]
        separator = syntax.separators[index]
        if command_name in {"export", "declare", "typeset", "readonly", "unset"}:
            for word in arguments:
                name = word.split("=", 1)[0]
                if name in {"HOME", "CDPATH", "PWD", "OLDPWD"}:
                    directory_environment.add(name)

        if command_name == "cd":
            target = next((value for value in arguments if value == "-" or not value.startswith("-")), str(HOME))
            uncertain_home = "HOME" in directory_environment and (not arguments or target == "~" or target.startswith("~/")
                                                                    or any(marker in target for marker in ("$HOME", "${HOME}")))
            target = target.replace("${HOME}", str(HOME)).replace("$HOME", str(HOME))
            absolute = Path(os.path.expanduser(target)).is_absolute()
            search_path = "CDPATH" in directory_environment and not absolute and not target.startswith(("./", "../"))
            if target == "-" or uncertain_home or search_path or any(marker in target for marker in ("$", "`", "*", "?", "[")):
                targets: set[Path | None] = {None}
            else:
                targets = {resolve(target, str(base or cwd)) if base is not None or absolute else None
                           for base in possible_cwds}
            seen_cwds |= possible_cwds | targets
            if separator == "&&":
                possible_cwds = targets
            elif separator not in {"|", "|&"}:
                possible_cwds |= targets
            continue
        if command_name in {"pushd", "popd", "chdir", "source", "."}:
            possible_cwds = {None}
        if command_name == "apply_patch":
            documents = [body for owner, body in syntax.heredocs if owner == index]
            documents.extend(value for value in arguments if value.lstrip().startswith("*** Begin Patch"))
            if not documents or any(not is_complete_patch_envelope(body) for body in documents):
                errors.append("Installed-artifact guard could not resolve a complete patch destination envelope")
            for body in documents:
                for destination in patch_paths(body):
                    add_destination(destination, "patch")

        positional = positional_arguments(arguments)
        destinations: list[str] = []
        if command_name in mutators_all_args:
            destinations.extend(positional)
        elif command_name in mutators_last_arg and positional:
            destinations.append(positional[-1])
        elif command_name in {"chmod", "chown"} and len(positional) > 1:
            destinations.extend(positional[1:])
        elif command_name == "sed" and any(
            flag == "-i"
            or flag.startswith("-i")
            or flag.startswith("--in-place")
            for flag in arguments
        ):
            destinations.extend(positional)
        elif command_name == "perl" and any(
            flag.startswith("-") and "i" in flag[1:] for flag in arguments
        ):
            destinations.extend(positional)

        for destination in destinations:
            add_destination(destination, "mutation")
        if wrapped_directory:
            possible_cwds = parent_cwds
    return paths, errors


def candidates(payload: dict) -> tuple[list[Path], list[str]]:
    tool_input = payload.get("tool_input") or {}
    cwd = str(payload.get("cwd") or "")
    values: list[str] = []
    paths: list[Path] = []
    errors: list[str] = []
    if "workdir" in tool_input:
        workdir = tool_input["workdir"]
        resolved_workdir = resolve(workdir, cwd) if isinstance(workdir, str) else None
        if resolved_workdir is None:
            return [], ["Installed-artifact guard could not resolve the native workdir"]
        cwd = str(resolved_workdir)
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str):
            values.append(value)
    for key in ("patch",):
        value = tool_input.get(key)
        if isinstance(value, str):
            values.extend(patch_paths(value))
    for key in ("command", "cmd"):
        value = tool_input.get(key)
        if isinstance(value, str):
            # Codex Desktop currently reports a nested ``apply_patch`` call
            # through an outer orchestration alias. In that shape the command
            # value is the complete patch document itself, not shell text.
            # Parse it as a structured patch so apostrophes or other prose do
            # not become false shell-syntax failures, while protected paths
            # remain blocked by the same policy below.
            if value.lstrip().startswith("*** Begin Patch"):
                if not is_complete_patch_envelope(value):
                    errors.append(
                        "Installed-artifact guard received an incomplete or mixed patch envelope"
                    )
                else:
                    values.extend(patch_paths(value))
            else:
                shell_paths, shell_errors = shell_write_paths(value, cwd)
                paths.extend(shell_paths)
                errors.extend(shell_errors)
    paths.extend(
        path for value in values if (path := resolve(value, cwd)) is not None
    )
    return paths, errors


MANIFEST_FIELDS = ("installed_by", "source_repo", "source_path", "source_commit")
ABSENT_OWNER = (
    "no readable .source.json beside this artifact; "
    "run every declared installer status"
)


def manifest_owner(manifest: Path) -> str | None:
    """Return the installer sentence from one manifest, or None when it is unreadable.

    Only the four provenance fields are echoed, never the file body or any other
    key, so a malformed or foreign file cannot leak content into a hook reason.
    Each field is collapsed to single spaces and stripped of every non-printable
    character, so a terminal escape or NUL in a manifest never reaches the reason;
    a field with nothing printable left counts as missing.
    """
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    values: dict[str, str] = {}
    for field in MANIFEST_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str):
            return None
        visible = "".join(
            character
            for character in value
            if character.isprintable() or character.isspace()
        )
        values[field] = " ".join(visible.split())
        if not values[field]:
            return None
    return (
        f"installed by {values['installed_by']} from {values['source_repo']} "
        f"({values['source_path']}) at {values['source_commit']}; "
        "edit that source, then run that installer's update"
    )


def installed_owner(path: Path) -> str:
    """Name the installer owning a protected artifact via the nearest .source.json.

    The walk stops at the nearest entry that exists in any form and attributes the
    artifact only when that entry is a regular, non-symlink file; a symlink or a
    directory there is the absence sentence, never an ancestor's installer. Every
    probe is an ``os.path`` predicate, which swallows every OSError, so an
    unreadable directory on the walk still yields a block instead of a crash.
    """
    for root in PROTECTED_ROOTS:
        if root not in path.parents:
            continue
        for directory in (path, *path.parents):
            if directory == root:
                break
            manifest = directory / ".source.json"
            if not os.path.lexists(manifest):
                continue
            regular = os.path.isfile(manifest) and not os.path.islink(manifest)
            return (manifest_owner(manifest) if regular else None) or ABSENT_OWNER
    return ABSENT_OWNER


def reason_for(path: Path) -> str | None:
    if path in GENERATED_RULES:
        return (
            f"{path} is generated. Edit the canonical source document "
            "and run the agent control installer."
        )
    if any(path == root or root in path.parents for root in PROTECTED_ROOTS):
        return (
            f"{path} is an installed skill artifact. Edit its source repository, "
            "commit and push the source, then reinstall and verify drift. "
            f"Provenance: {installed_owner(path)}."
        )
    if path.name == "CLAUDE.md" and path.is_file():
        try:
            if path.read_text(encoding="utf-8").strip() == "@AGENTS.md":
                return f"{path} is an import adapter. Edit the sibling AGENTS.md."
        except OSError:
            return f"{path} could not be verified; refusing the write."
    return None


def deny(client: str, reason: str) -> int:
    if client == "claude":
        print(json.dumps({"decision": "block", "reason": reason}))
    else:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    }
                }
            )
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=("claude", "codex"), required=True)
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        return deny(args.client, f"Installed-artifact guard could not parse hook input: {exc}")

    paths, errors = candidates(payload)
    if errors:
        return deny(args.client, errors[0])
    for path in paths:
        reason = reason_for(path)
        if reason:
            return deny(args.client, reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
