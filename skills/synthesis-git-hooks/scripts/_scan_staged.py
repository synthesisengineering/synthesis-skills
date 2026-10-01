#!/usr/bin/env python3
"""Byte-preserving Git added-line scanning; paths and patterns are never shell code."""

from __future__ import annotations

import argparse
import ast
import json
import hashlib
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time

MAX_DIFF_BYTES = 256 * 1024 * 1024
MAX_ERROR_BYTES = 1024 * 1024
MAX_MESSAGE_BYTES = 1024 * 1024
MAX_REPORT_BYTES = 16 * 1024
SCAN_SECONDS = 60
MAX_CONTEXT_BYTES = 32 * 1024 * 1024
MAX_CONTEXT_FILES = 1024
HUNK = re.compile(rb"^@@ -[0-9]+(?:,([0-9]+))? \+[0-9]+(?:,([0-9]+))? @@(?: .*)?$")


class ScanError(RuntimeError):
    pass


def stop(child: subprocess.Popen) -> None:
    try:
        child.wait(timeout=0.1)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    child.wait(timeout=2)


def remaining(deadline: float) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise ScanError("staged scanner exceeded its 60-second bound")
    return value


def bounded_git(deadline: float, arguments: list[str] | None = None) -> bytes:
    argv = [
        "git",
        "--no-pager",
        "diff",
        "--cached",
        "--no-ext-diff",
        "--no-textconv",
        "--text",  # Binary presentation and -diff attributes cannot hide bytes.
        "--no-color",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        "-C",
        "--find-copies-harder",
        "--diff-filter=AMCR",
        "-U0",
    ]
    if arguments is not None:
        argv = ["git", "--no-pager", *arguments]
    child = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True
    )
    streams: dict[int, bytearray] = {
        child.stdout.fileno(): bytearray(),
        child.stderr.fileno(): bytearray(),
    }
    output_fd = child.stdout.fileno()
    selector = selectors.DefaultSelector()
    try:
        for stream in (child.stdout, child.stderr):
            selector.register(stream, selectors.EVENT_READ)
        while selector.get_map():
            events = selector.select(remaining(deadline))
            if not events:
                raise ScanError("Git diff acquisition timed out")
            for key, _ in events:
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                target = streams[key.fd]
                target.extend(chunk)
                if len(target) > (
                    MAX_DIFF_BYTES if key.fd == output_fd else MAX_ERROR_BYTES
                ):
                    raise ScanError("Git diff acquisition exceeded its byte bound")
        status = child.wait(timeout=remaining(deadline))
        if status:
            error = bytes(streams[child.stderr.fileno()]).decode(
                "utf-8", "backslashreplace"
            )
            raise ScanError(f"git diff exited {status}: {error}")
        return bytes(streams[output_fd])
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise ScanError(f"Git diff acquisition failed: {exc}") from exc
    finally:
        selector.close()
        child.stdout.close()
        child.stderr.close()
        stop(child)


def grep(
    data: bytes,
    pattern: str,
    deadline: float,
    *,
    invert: bool = False,
    ignore_case: bool = True,
) -> bytes:
    # Keep the owner's ERE implementation and locale. -a prevents arbitrary
    # Git text bytes (including late NULs) from becoming a binary-match summary.
    original = data.split(b"\n")
    if original and original[-1] == b"":
        original.pop()
    # BSD grep can silently miss a valid Unicode/ASCII match after an invalid
    # byte even with -a. Present a deterministic Unicode view to the unchanged
    # locale/ERE engine, then map line numbers back to exact original bytes.
    # Invalid-byte lines never gain an allowlist exemption from that view.
    decoded = [line.decode("utf-8", "replace").encode("utf-8") for line in original]
    invalid = {
        index for index, (raw, view) in enumerate(zip(original, decoded)) if raw != view
    }
    view = b"\n".join(decoded) + (b"\n" if decoded else b"")
    argv = ["grep", "-a", "-n", "-E"]
    if ignore_case:
        argv.append("-i")
    if invert:
        argv.append("-v")
    argv.extend(["-e", pattern])
    child = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        out, error = child.communicate(view, timeout=remaining(deadline))
        if child.returncode not in (0, 1):
            raise ScanError(
                f"grep rejected policy or input (exit {child.returncode}): "
                + error.decode("utf-8", "backslashreplace")
            )
        if len(out) > 4 * MAX_DIFF_BYTES or len(error) > MAX_ERROR_BYTES:
            raise ScanError("pattern scanning exceeded its output bound")
        selected = set(invalid) if invert else set()
        prior = -1
        for record in out.split(b"\n"):
            if not record:
                continue
            number, separator, text = record.partition(b":")
            if not separator or not number.isdigit():
                raise ScanError("grep returned malformed line evidence")
            index = int(number) - 1
            if (
                index <= prior
                or not 0 <= index < len(original)
                or text != decoded[index]
            ):
                raise ScanError("grep line evidence does not bind the original input")
            prior = index
            selected.add(index)
        return b"".join(original[index] + b"\n" for index in sorted(selected))
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise ScanError(f"pattern scanning failed: {exc}") from exc
    finally:
        stop(child)
        for stream in (child.stdin, child.stdout, child.stderr):
            if stream is not None:
                stream.close()


def destination(header: bytes) -> bytes:
    value = header[4:]
    if value.startswith(b'"'):
        out = bytearray()
        index = 1
        escapes = {
            ord("a"): 7,
            ord("b"): 8,
            ord("t"): 9,
            ord("n"): 10,
            ord("v"): 11,
            ord("f"): 12,
            ord("r"): 13,
            ord('"'): 34,
            ord("\\"): 92,
        }
        while index < len(value):
            char = value[index]
            index += 1
            if char == 34:
                if value[index:] not in (b"", b"\t"):
                    raise ScanError("unexpected suffix in Git destination header")
                value = bytes(out)
                break
            if char == 92:
                if index >= len(value):
                    raise ScanError("incomplete Git path escape")
                char = value[index]
                if 48 <= char <= 55:
                    octal = value[index : index + 3]
                    if len(octal) != 3 or any(c < 48 or c > 55 for c in octal):
                        raise ScanError("invalid Git octal path escape")
                    number = int(octal, 8)
                    if number > 255:
                        raise ScanError("Git path escape exceeds byte range")
                    out.append(number)
                    index += 3
                    continue
                if char not in escapes:
                    raise ScanError("unknown Git path escape")
                out.append(escapes[char])
                index += 1
            else:
                out.append(char)
        else:
            raise ScanError("unterminated Git destination header")
    else:
        value = value.removesuffix(b"\t")
    if not value.startswith(b"b/") or b"\0" in value:
        raise ScanError("unrecognized Git destination header")
    return value[2:]


def added_lines(
    diff: bytes, exclusion: str, deadline: float, records: list | None = None
) -> tuple[bytes, bytes]:
    all_lines = bytearray()
    selected = bytearray()
    path = None
    old_left = new_left = 0
    new_number = 0
    exclude = False
    cache: dict[bytes, bool] = {}
    for line in diff.split(b"\n"):
        remaining(deadline)
        if old_left or new_left:
            if line.startswith(b"\\ No newline at end of file"):
                continue
            if not line or line[:1] not in (b"+", b"-", b" "):
                raise ScanError("malformed or truncated Git hunk")
            prefix = line[:1]
            if prefix != b"+":
                old_left -= 1
            if prefix != b"-":
                new_left -= 1
            if min(old_left, new_left) < 0:
                raise ScanError("Git hunk length mismatch")
            if prefix == b"+":
                # Preserve the leading '+' as the historical scanner did.
                all_lines.extend(line + b"\n")
                if records is not None:
                    records.append((path, new_number, line[1:]))
                if not exclude:
                    selected.extend(line + b"\n")
            if prefix != b"-":
                new_number += 1
            continue
        if line.startswith(b"diff --git "):
            path = None
            exclude = False
        elif line.startswith(b"+++ "):
            if path is not None:
                raise ScanError("duplicate Git destination header")
            path = destination(line)
            if path not in cache:
                # A line-oriented ERE cannot safely exclude a multi-line Git
                # pathname. Scan it rather than treating one segment as a path.
                try:
                    path.decode("utf-8", "strict")
                    valid_path = b"\n" not in path
                except UnicodeError:
                    valid_path = False
                cache[path] = bool(
                    exclusion
                    and valid_path
                    and grep(path + b"\n", exclusion, deadline, ignore_case=False)
                )
            exclude = cache[path]
        elif line.startswith(b"@@ "):
            match = HUNK.fullmatch(line)
            if path is None or not match:
                raise ScanError("unbound or malformed Git hunk")
            new_number = int(
                line.split(b" +", 1)[1].split(b" ", 1)[0].split(b",", 1)[0]
            )
            old_left = int(match[1]) if match[1] is not None else 1
            new_left = int(match[2]) if match[2] is not None else 1
        elif line.startswith(b"+"):
            raise ScanError("added Git line outside a declared hunk")
    if old_left or new_left:
        raise ScanError("truncated Git hunk")
    return bytes(all_lines), bytes(selected)


def message_lines(path: str, deadline: float) -> bytes:
    remaining(deadline)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_MESSAGE_BYTES:
            raise ScanError("commit message must be a bounded regular file")
        raw = stream.read(MAX_MESSAGE_BYTES + 1)
        after = os.fstat(stream.fileno())

    def identity(st):
        return (
            st.st_dev,
            st.st_ino,
            st.st_mode,
            st.st_nlink,
            st.st_size,
            st.st_mtime_ns,
            st.st_ctime_ns,
        )

    if (
        len(raw) > MAX_MESSAGE_BYTES
        or identity(before) != identity(after)
        or identity(after) != identity(os.lstat(path))
    ):
        raise ScanError("commit message changed during bounded observation")
    remaining(deadline)
    return b"\n".join(line for line in raw.split(b"\n") if not line.startswith(b"#"))


# Only these literal vocabulary entries have a syntax-aware interpretation.
# Every other configured ERE, including duplicates in other groups, keeps its
# ordinary unconditional matching semantics. This is policy data, not a grant.
MARKER_NAMES = tuple(
    "BEGIN " + family + "PRIVATE KEY"
    for family in ("RSA ", "OPENSSH ", "EC ", "PGP ", "", "ENCRYPTED ")
)


def rule_policy(value: str | None, tier0: str, active: str) -> dict | None:
    if value is None:
        return None  # Direct scanner calls remain conservative without typed policy.
    try:
        policy = json.loads(value)
    except (ValueError, TypeError) as exc:
        raise ScanError("invalid typed marker policy") from exc
    if (
        not isinstance(policy, dict)
        or set(policy)
        != {"version", "markers", "credentials", "exposure", "tier0", "active"}
        or type(policy["version"]) is not int
        or policy["version"] != 1
        or not isinstance(policy["markers"], list)
        or any(
            not isinstance(x, str) or x not in MARKER_NAMES for x in policy["markers"]
        )
        or len(policy["markers"]) != len(set(policy["markers"]))
        or any(
            not isinstance(policy[x], str)
            for x in ("credentials", "exposure", "tier0", "active")
        )
        or policy["tier0"] != tier0
        or policy["active"] != active
    ):
        raise ScanError("typed marker policy does not bind scanner expressions")
    return policy


def staged_context(index: bytes, records: list, deadline: float) -> dict[bytes, bytes]:
    """Read content-addressed index blobs, never mutable worktree files."""
    wanted = {path for path, _, _ in records}
    if len(wanted) > MAX_CONTEXT_FILES:
        raise ScanError("marker context exceeded its file bound")
    objects = {}
    for entry in index.split(b"\0"):
        remaining(deadline)
        if not entry:
            continue
        header, sep, path = entry.partition(b"\t")
        fields = header.split(b" ")
        if not sep or len(fields) != 3:
            raise ScanError("malformed staged index evidence")
        mode, oid, stage = fields
        if path not in wanted:
            continue
        if (
            stage != b"0"
            or path in objects
            or not re.fullmatch(rb"[0-9a-f]{40}|[0-9a-f]{64}", oid)
        ):
            raise ScanError("unmerged or malformed staged context")
        objects[path] = (mode, oid)
    if set(objects) != wanted:
        raise ScanError("staged context path is missing")
    blobs = {}
    total = 0
    for path in sorted(wanted):
        mode, oid = objects[path]
        if mode == b"160000":
            # Gitlink text is a commit identifier, not blob content. Still scan
            # the original added lines; never classify them as detection rules.
            blobs[path] = b""
            continue
        if mode not in (b"100644", b"100755", b"120000"):
            raise ScanError("unsupported staged context mode")
        raw = bounded_git(deadline, ["cat-file", "blob", oid.decode("ascii")])
        total += len(raw)
        if total > MAX_CONTEXT_BYTES:
            raise ScanError("marker context exceeded its byte bound")
        payload = b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
        digest = (
            hashlib.sha1(payload) if len(oid) == 40 else hashlib.sha256(payload)
        ).hexdigest()
        if digest.encode("ascii") != oid:
            raise ScanError("staged blob does not match its object identity")
        blobs[path] = raw
    # Bind every diff line and line number to the captured index object.
    lines = {path: raw.split(b"\n") for path, raw in blobs.items()}
    for path, number, raw in records:
        if objects[path][0] == b"160000":
            continue
        if not 1 <= number <= len(lines[path]) or lines[path][number - 1] != raw:
            raise ScanError("Git diff does not bind captured staged content")
    return blobs


def load_rule_parser(deadline: float):
    """Reuse the installed config grammar from captured source, without pyc reuse."""
    remaining(deadline)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_load_config.py")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > 1024 * 1024:
            raise ScanError("rule parser source must be a bounded regular file")
        raw = bytearray()
        while len(raw) <= 1024 * 1024:
            remaining(deadline)
            part = os.read(fd, 65536)
            if not part:
                break
            raw.extend(part)
        after = os.fstat(fd)

        def identity(info):
            return (
                info.st_dev,
                info.st_ino,
                info.st_mode,
                info.st_nlink,
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
            )

        if (
            len(raw) != before.st_size
            or identity(before) != identity(after)
            or identity(after) != identity(os.lstat(path))
        ):
            raise ScanError("rule parser source changed during capture")
    finally:
        os.close(fd)
    namespace = {"__name__": "_captured_marker_rule_parser", "__file__": path}
    exec(compile(bytes(raw), path, "exec"), namespace)
    return namespace["parse_simple_yaml"], namespace["ConfigError"]


def detection_rule_lines(raw: bytes, markers: list[str], parser) -> set[int]:
    """Recognize narrow data-only rule syntax, never filenames or quotes alone.

    YAML: a complete private_key_markers sequence at document root or directly
    inside tier_0_always, containing only exact bare marker strings. Python:
    a data-only module of raw-string private_key_marker assignments. No parser
    recovery, arbitrary expression evaluation, aliases, or key-material values.
    Other content still receives all credential/exposure scans.
    """
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeError:
        return set()
    if "\0" in text:
        return set()
    lines = text.split("\n")
    allowed = set(markers)
    accepted = set()
    parse_yaml, config_error = parser
    try:
        document = parse_yaml(text)
        # Parsing the complete document prevents malformed neighboring bodies
        # from borrowing a rule-looking key or indentation as an exemption.
        yaml_valid = isinstance(document, dict)
    except (config_error, ValueError, RecursionError):
        yaml_valid = False
    parents = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        while parents and parents[-1][0] >= indent:
            parents.pop()
        header = re.fullmatch(r" *([A-Za-z_][A-Za-z_0-9]*): *(?:#.*)?", line)
        if not header:
            continue
        name = header[1]
        eligible = (
            yaml_valid
            and name == "private_key_markers"
            and (
                indent == 0 or (len(parents) == 1 and parents[0][1] == "tier_0_always")
            )
        )
        if eligible:
            found = []
            item_indent = None
            valid = True
            for offset in range(index + 1, len(lines)):
                item = lines[offset]
                if not item.strip() or item.lstrip().startswith("#"):
                    continue
                depth = len(item) - len(item.lstrip(" "))
                if depth <= indent:
                    break
                match = re.fullmatch(r"( +)- (['\"])([^'\"\\]+)\2 *(?:#.*)?", item)
                if not match or match[3] not in allowed:
                    valid = False
                    break
                if item_indent is None:
                    item_indent = len(match[1])
                if len(match[1]) != item_indent:
                    valid = False
                    break
                # A second marker in a trailing comment is still material.
                suffix = item[match.end(3) + 1 :]
                if any(marker.lower() in suffix.lower() for marker in markers):
                    valid = False
                    break
                found.append(offset + 1)
            if valid and found:
                accepted.update(found)
        parents.append((indent, name))
    # A Python rule module has one meaning: raw constant declarations only.
    try:
        module = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return accepted
    python_lines = set()
    for node in module.body:
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "private_key_marker"
            and isinstance(node.value, ast.Constant)
            and node.value.value in allowed
            and node.lineno == node.end_lineno
            and re.fullmatch(
                r" *private_key_marker *= *[rR](['\"])[^'\"\\]+\1 *",
                lines[node.lineno - 1],
            )
        ):
            return accepted
        python_lines.add(node.lineno)
    return accepted | python_lines


def marker_view(line: bytes) -> bytes:
    # Escaped JSON/Python string content remains material. Decoding only ASCII
    # escapes cannot create a rule exemption; rule syntax is checked on originals.
    return re.sub(
        rb"\\(?:u00([0-9a-fA-F]{2})|x([0-9a-fA-F]{2}))",
        lambda match: bytes([int(match[1] or match[2], 16)]),
        line,
    ).lower()


def complete_inline_key_regions(line: bytes, markers: list[bytes]) -> bool:
    """Prove closed regions in one complete JSON value, never by substring.

    An unchanged JSON record can contain a complete escaped multi-line key.
    Its matching footer closes only that value, not an earlier open raw region.
    All marker-bearing strings, including object keys, must prove closure.
    """
    try:
        pending = [json.loads(line.decode("utf-8", "strict"))]
    except (UnicodeError, ValueError, RecursionError):
        return False
    found = False
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
        elif isinstance(value, str):
            encoded = value.lower().encode("utf-8")
            relevant = [marker for marker in markers if marker in encoded]
            if not relevant:
                continue
            if len(relevant) != 1:
                return False
            marker = relevant[0]
            suffix = b" block" if marker == b"begin pgp private key" else b""
            header = b"-----" + marker + suffix + b"-----"
            footer = (
                b"-----" + marker.replace(b"begin ", b"end ", 1) + suffix + b"-----"
            )
            lines = encoded.strip().splitlines()
            if (
                len(lines) < 2
                or lines[0].strip() != header
                or lines[-1].strip() != footer
                or any(
                    b"-----begin " in item or b"-----end " in item
                    for item in lines[1:-1]
                )
            ):
                return False
            found = True
    return found


def material_lines(
    blobs: dict[bytes, bytes], records: list, markers: list[str], deadline: float
) -> bytes:
    added = {}
    for path, number, raw in records:
        added.setdefault(path, {})[number] = raw
    hits = []
    parser = load_rule_parser(deadline)
    encoded = [value.lower().encode("ascii") for value in markers]
    for path, changes in added.items():
        remaining(deadline)
        raw = blobs[path]
        rules = detection_rule_lines(raw, markers, parser)
        opened = []
        for number, line in enumerate(raw.split(b"\n"), 1):
            remaining(deadline)
            view = marker_view(line)
            found = next((value for value in encoded if value in view), None)
            # A recognized exact bare scalar is a rule, not a key header. A
            # neighboring invalid/body-bearing sequence invalidates that proof.
            inline_complete = found and complete_inline_key_regions(line, encoded)
            if found and number not in rules and not inline_complete:
                suffix = b" block" if found == b"begin pgp private key" else b""
                opened.append(
                    b"-----" + found.replace(b"begin ", b"end ", 1) + suffix + b"-----"
                )
            if number in changes and (opened or (found and number not in rules)):
                hits.append(b"+" + changes[number] + b"\n")
            # Bare END words in comments are not an armored footer. A partial
            # footer keeps the region open, so a later added body cannot escape.
            if opened:
                # A quoted example, comment, wrong-family or partial footer is
                # not evidence that an existing private region has ended.
                if view.strip() == opened[-1]:
                    opened.pop()
        if not raw:  # Gitlink additions retain conservative literal matching.
            for line in changes.values():
                if any(value in marker_view(line) for value in encoded):
                    hits.append(b"+" + line + b"\n")
    return b"".join(hits)


def scan(
    tier0: str,
    active: str,
    allowlist: str,
    exclusion: str,
    message: str | None = None,
    *,
    mandatory: str = "",
    marker_policy: str | None = None,
) -> bytes:
    if not tier0 or not active:
        raise ScanError("credential and active patterns must be nonempty")
    deadline = time.monotonic() + SCAN_SECONDS
    policy = rule_policy(marker_policy, tier0, active)
    credentials = tier0 if policy is None else policy["credentials"]
    exposure = active if policy is None else policy["exposure"]
    markers = [] if policy is None else policy["markers"]
    for pattern in (
        tier0,
        active,
        allowlist,
        exclusion,
        mandatory,
        credentials,
        exposure,
    ):
        if pattern:
            grep(b"", pattern, deadline)
    records = []
    index = None
    if message is None:
        if markers:
            index = bounded_git(deadline, ["ls-files", "--stage", "-z"])
        raw = bounded_git(deadline)
        unfiltered, selected = added_lines(raw, exclusion, deadline, records)
        blobs = staged_context(index, records, deadline) if markers else {}
    else:
        unfiltered = selected = message_lines(message, deadline)
        blobs = {b"message": unfiltered}
        records = [
            (b"message", number, line)
            for number, line in enumerate(unfiltered.split(b"\n"), 1)
        ]
    matches = grep(unfiltered, credentials, deadline) if credentials else b""
    if not matches and markers:
        matches = material_lines(blobs, records, markers, deadline)
    if not matches and mandatory:
        matches = grep(unfiltered, mandatory, deadline)
    if not matches and exposure:
        matches = grep(selected, exposure, deadline)
        if matches and allowlist:
            matches = grep(matches, allowlist, deadline, invert=True)
    if (
        index is not None
        and bounded_git(deadline, ["ls-files", "--stage", "-z"]) != index
    ):
        raise ScanError("staged index changed during marker scan")
    return b"\n".join(matches.split(b"\n")[:20]).rstrip(b"\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("tier0", "active", "allowlist", "exclusion"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--message")
    parser.add_argument("--marker-policy")
    parser.add_argument("--mandatory", default="")
    args = parser.parse_args()
    try:
        matches = scan(
            args.tier0,
            args.active,
            args.allowlist,
            args.exclusion,
            args.message,
            mandatory=args.mandatory,
            marker_policy=args.marker_policy,
        )
    except (ScanError, OSError, ValueError) as exc:
        print(f"staged scanner failed closed: {exc}", file=sys.stderr)
        return 2
    if matches:
        # Terminal-safe representation, after byte-exact matching. Never drop
        # undecodable bytes or reinterpret them as missing sensitive content.
        report = matches[:MAX_REPORT_BYTES]
        decoded = report.decode("utf-8", "backslashreplace")
        print(
            "".join(
                c if ord(c) >= 32 or c in "\n\t" else f"\\x{ord(c):02x}"
                for c in decoded
            )
        )
        if len(matches) > MAX_REPORT_BYTES:
            print(
                f"[matched evidence display truncated: {len(matches)} bytes; SHA256 {hashlib.sha256(matches).hexdigest()}]"
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
