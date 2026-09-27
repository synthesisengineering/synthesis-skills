#!/usr/bin/env python3
"""Byte-preserving Git added-line scanning; paths and patterns are never shell code."""

from __future__ import annotations

import argparse
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


def bounded_git(deadline: float) -> bytes:
    argv = [
        "git",
        "--no-pager",
        "diff",
        "--cached",
        "--no-ext-diff",
        "--no-textconv",
        "--no-color",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        "-C",
        "--find-copies-harder",
        "--diff-filter=AMCR",
        "-U0",
    ]
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


def added_lines(diff: bytes, exclusion: str, deadline: float) -> tuple[bytes, bytes]:
    all_lines = bytearray()
    selected = bytearray()
    path = None
    old_left = new_left = 0
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
                if not exclude:
                    selected.extend(line + b"\n")
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


def scan(
    tier0: str, active: str, allowlist: str, exclusion: str, message: str | None = None
) -> bytes:
    if not tier0 or not active:
        raise ScanError("credential and active patterns must be nonempty")
    deadline = time.monotonic() + SCAN_SECONDS
    for pattern in (tier0, active, allowlist, exclusion):
        if pattern:
            grep(b"", pattern, deadline)
    if message is None:
        raw = bounded_git(deadline)
        unfiltered, selected = added_lines(raw, exclusion, deadline)
    else:
        unfiltered = selected = message_lines(message, deadline)
    matches = grep(unfiltered, tier0, deadline)
    if not matches:
        matches = grep(selected, active, deadline)
        if matches and allowlist:
            matches = grep(matches, allowlist, deadline, invert=True)
    return b"\n".join(matches.split(b"\n")[:20]).rstrip(b"\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("tier0", "active", "allowlist", "exclusion"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--message")
    args = parser.parse_args()
    try:
        matches = scan(
            args.tier0, args.active, args.allowlist, args.exclusion, args.message
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
