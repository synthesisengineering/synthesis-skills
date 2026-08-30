#!/usr/bin/env python3
"""Dispatch a prompt to OpenAI Codex non-interactively, and fail loudly instead of hanging.

`codex exec` reads stdin when stdin is not closed. Backgrounded from a shell that leaves stdin
open, it prints "Reading additional input from stdin..." and blocks forever. On 2026-08-30 that
cost two and a half hours: the process sat at 0.0% CPU with a 39-byte output file while the
dispatching agent assumed a long review was in progress. The first dispatch that day had worked
only because its shell happened to close stdin.

Silence is indistinguishable from work, which is why this wrapper exists rather than a note in
a skill telling agents to remember a redirect.

Three guarantees:

1. **stdin is always /dev/null.** The failure cannot recur by forgetting a redirect.
2. **A watchdog watches output growth, not wall time.** A review legitimately takes many
   minutes; what is never legitimate is producing nothing while consuming no CPU. Stall is
   defined as "output file unchanged for --stall-seconds", which distinguishes a slow model
   from a blocked process.
3. **The binary is located, not assumed.** It is not on PATH in a normal shell; it lives under
   ~/.codex/plugins/. An agent that shells out to `codex` gets "command not found" and may
   wrongly conclude the capability does not exist. It does.

    python3 codex_dispatch.py --prompt-file brief.md --out review.txt
    python3 codex_dispatch.py --prompt "one-line question" --stall-seconds 300
    python3 codex_dispatch.py --doctor
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import time

CANDIDATES = [
    pathlib.Path.home() / ".codex/plugins/.plugin-appserver/codex",
    pathlib.Path("/usr/local/bin/codex"),
    pathlib.Path("/opt/homebrew/bin/codex"),
]
STALL_SECONDS = 420          # no new output for this long, with the file non-growing = hung
POLL_SECONDS = 10
HANG_MARKER = "Reading additional input from stdin"


def find_binary() -> pathlib.Path | None:
    which = shutil.which("codex")
    if which:
        return pathlib.Path(which)
    for c in CANDIDATES:
        if c.is_file() and os.access(c, os.X_OK):
            return c
    # Last resort: a bounded search of the codex plugin tree.
    root = pathlib.Path.home() / ".codex"
    if root.is_dir():
        for p in root.glob("plugins/**/codex"):
            if p.is_file() and os.access(p, os.X_OK):
                return p
    return None


def doctor() -> int:
    b = find_binary()
    print(f"  binary            : {b or 'NOT FOUND'}")
    if not b:
        print("  Codex is unreachable from this machine. Do not report it as unavailable")
        print("  without running this check - the binary is off PATH by default.")
        return 1
    on_path = shutil.which("codex") is not None
    print(f"  on PATH           : {'yes' if on_path else 'no (expected; this wrapper resolves it)'}")
    try:
        v = subprocess.run([str(b), "--version"], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=60)
        print(f"  version           : {v.stdout.strip() or v.stderr.strip()}")
    except Exception as e:
        print(f"  version           : FAILED {e}")
        return 1
    print("  smoke test        : dispatching a trivial prompt...")
    rc, out, why = dispatch(b, "Reply with exactly: CODEX_OK", None, 120, quiet=True)
    ok = "CODEX_OK" in out
    print(f"  authenticated     : {'yes' if ok else 'NO - ' + why}")
    return 0 if ok else 1


def dispatch(binary: pathlib.Path, prompt: str, out_path: pathlib.Path | None,
             stall_seconds: int, quiet: bool = False) -> tuple[int, str, str]:
    """Run codex exec with stdin closed and a stall watchdog. Returns (rc, output, reason)."""
    tmp = out_path or pathlib.Path(
        os.environ.get("TMPDIR", "/tmp")) / f"codex-dispatch-{os.getpid()}.txt"
    tmp.parent.mkdir(parents=True, exist_ok=True)

    with tmp.open("w", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            [str(binary), "exec", "--skip-git-repo-check", prompt],
            stdin=subprocess.DEVNULL,        # guarantee 1 - the whole point of this wrapper
            stdout=fh, stderr=subprocess.STDOUT,
        )

        last_size, last_change = -1, time.time()
        while proc.poll() is None:
            time.sleep(POLL_SECONDS)
            size = tmp.stat().st_size if tmp.exists() else 0
            if size != last_size:
                last_size, last_change = size, time.time()
                if not quiet:
                    print(f"    ... {size:,} bytes", flush=True)
                continue
            idle = time.time() - last_change
            if idle >= stall_seconds:
                head = tmp.read_text(encoding="utf-8", errors="replace")[:400]
                reason = "stalled"
                if HANG_MARKER in head:
                    reason = ("BLOCKED ON STDIN - the known hang. stdin was not closed. "
                              "This wrapper closes it, so seeing this means codex was "
                              "invoked directly somewhere else.")
                else:
                    reason = (f"no output growth for {int(idle)}s at {size:,} bytes; "
                              "treating as hung")
                proc.kill()
                proc.wait(timeout=30)
                return 124, tmp.read_text(encoding="utf-8", errors="replace"), reason

    return proc.returncode, tmp.read_text(encoding="utf-8", errors="replace"), ""


def final_report(raw: str) -> str:
    """Codex echoes its tool use; the report follows the last bare 'codex' line."""
    lines = [l for l in raw.splitlines() if not l.startswith("hook: ")]
    marks = [i for i, l in enumerate(lines) if l.strip() == "codex"]
    return "\n".join(lines[marks[-1] + 1:] if marks else lines)


def main() -> int:
    ap = argparse.ArgumentParser(allow_abbrev=False, description=__doc__.splitlines()[0])
    ap.add_argument("--prompt")
    ap.add_argument("--prompt-file")
    ap.add_argument("--out")
    ap.add_argument("--stall-seconds", type=int, default=STALL_SECONDS)
    ap.add_argument("--report-only", action="store_true",
                    help="print just the final report, not the tool-use trace")
    ap.add_argument("--doctor", action="store_true")
    args = ap.parse_args()

    if args.doctor:
        return doctor()

    if bool(args.prompt) == bool(args.prompt_file):
        ap.error("give exactly one of --prompt or --prompt-file")
    prompt = (pathlib.Path(args.prompt_file).read_text(encoding="utf-8")
              if args.prompt_file else args.prompt)

    binary = find_binary()
    if not binary:
        print("codex binary not found; run --doctor", file=sys.stderr)
        return 2

    out_path = pathlib.Path(args.out) if args.out else None
    rc, raw, reason = dispatch(binary, prompt, out_path, args.stall_seconds)

    if rc == 124:
        print(f"\n  DISPATCH FAILED: {reason}", file=sys.stderr)
        print(f"  partial output: {len(raw):,} bytes"
              + (f" in {out_path}" if out_path else ""), file=sys.stderr)
        return 124

    print(final_report(raw) if args.report_only else raw)
    return rc


if __name__ == "__main__":
    sys.exit(main())
