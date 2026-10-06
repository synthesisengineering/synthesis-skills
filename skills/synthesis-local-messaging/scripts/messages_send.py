# SPDX-License-Identifier: Apache-2.0
"""Send one approved iMessage to one person through the v5 send guard, at most once.

Run: python3 messages_send.py --to HANDLE --text-file FILE [--account ACCOUNT_ID]

1. An earlier attempt with this recipient and text refuses the send, unless that attempt is
   known not to have reached the send call: never resend after an uncertain outcome.
2. The one existing one-to-one iMessage chat with HANDLE is found read-only (messages_route.js).
   No chat is created; there is no SMS or RCS fallback and no group send.
3. The v5 send guard decides: the principal's forbidden phrases, then their single-use approval
   of this exact recipient and text. Without one it files a request and prints the code the
   principal types ("approve <code>"); after they do, run the identical command again.
4. The attempt is recorded, then exactly one send call runs through messages_transport.js. The
   text travels through a private file descriptor, never through argv or script source.

Prints one JSON object. status: dispatched (the send call returned: delivery and
acknowledgement stay unknown), not-sent (stopped before the send call), uncertain (anything
else: it may have sent, so it is never retried), refused or needs-approval (nothing was sent).
Exit 0 dispatched; 2 refused or needs-approval; 3 not-sent or uncertain.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle

HERE = Path(__file__).resolve().parent
HANDLE = re.compile(r"^(\+[1-9][0-9]{6,14}|[^\s@]+@[^\s@]+\.[^\s@]+)$")
TOOL = "imessage_send"
KEEP_SECONDS = 30 * 86400
# Errors messages_transport.js throws before its one send call, so nothing can have been sent.
PRE_SEND = ("descriptor required", "descriptor bound", "packet contract", "payload contract",
            "explicit route required", "text bound", "route bound", "recipient contract",
            "approval expired or unbounded", "selection bound", "ambiguous route", "account unavailable",
            "chat account changed", "one recipient required", "participant route changed")


class Refused(Exception):
    """Nothing was sent."""


def core():
    """The v5 guard and paths: from the plugin this script ships in, else the installed runtime."""
    for root in (HERE.parents[2], Path.home() / ".synthesis" / "v5" / "current"):
        if (root / "synthesis" / "guards.py").is_file():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from synthesis import guards, paths
            return guards, paths
    raise Refused("the synthesis v5 runtime is not installed, so the send guard cannot run; sending is blocked")


def osascript(script: Path, args: list, fd: int | None = None):
    """One fixed JXA program. Returns None on timeout; raises OSError when it cannot start."""
    try:
        return subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e", script.read_text(encoding="utf-8"), *args],
                              capture_output=True, text=True, timeout=15, pass_fds=(fd,) if fd is not None else ())
    except subprocess.TimeoutExpired:
        return None


def resolve_route(to: str, account: str | None) -> dict:
    try:
        done = osascript(HERE / "messages_route.js", [to])
    except OSError as exc:
        raise Refused(f"cannot run osascript: {exc}") from exc
    if done is None or done.returncode:
        raise Refused("could not read the Messages accounts and chats: " + ("timed out" if done is None else done.stderr.strip()[-500:]))
    routes = [r for r in json.loads(done.stdout)["routes"] if not account or r["account_id"] == account]
    usable = [r for r in routes if r["usable"]]
    if not usable:
        raise Refused(f"no existing one-to-one iMessage chat with {to} on a connected iMessage account. Start the "
                      "conversation in Messages first; this tool never creates a chat, sends SMS or sends to a group.")
    if len(usable) > 1:
        raise Refused(f"several iMessage chats match {to}; pass --account with one of: "
                      + ", ".join(sorted({r["account_id"] for r in usable})))
    chosen = usable[0]
    return {"account_id": chosen["account_id"], "service": "iMessage", "chat_id": chosen["chat_id"],
            "participant_id": chosen["participant_id"]}


def transport(to: str, text: str, route: dict, key: str) -> dict:
    payload = {"tool_name": "synthesis.messages.send",
               "tool_input": {"request_id": key, "destination": to, "text": text, "route": route}}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    packet = {"protocol": 1, "payload": payload, "digest": hashlib.sha256(canonical.encode()).hexdigest(),
              "expires_ms": int(time.time() * 1000) + 120000}
    with tempfile.TemporaryFile() as handle:  # unlinked and private to this process and its child
        handle.write(json.dumps(packet, ensure_ascii=False).encode("utf-8"))
        handle.flush()
        handle.seek(0)
        try:
            done = osascript(HERE / "messages_transport.js", [str(handle.fileno())], fd=handle.fileno())
        except OSError as exc:
            return {"status": "not-sent", "reason": f"osascript did not start: {exc}"}
    if done is None:
        return {"status": "uncertain", "reason": "the send call timed out and may have sent"}
    if done.returncode == 0:
        try:
            reply = json.loads(done.stdout)
        except ValueError:
            reply = {}
        if reply.get("phase") == "dispatched" and reply.get("request_digest") == packet["digest"]:
            return {"status": "dispatched", "delivery": "unknown", "acknowledgement": "unknown"}
        return {"status": "uncertain", "reason": "the send call returned without its dispatch report"}
    error = done.stderr.strip()[-500:]
    if any("Error: " + known in error for known in PRE_SEND):
        return {"status": "not-sent", "reason": error}
    return {"status": "uncertain", "reason": "the send call failed in a way that may follow sending: " + error}


def _save(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for old in path.parent.glob("*.json"):  # bounded: a record outlives the resend risk by weeks
        if old != path and time.time() - old.stat().st_mtime > KEEP_SECONDS:
            old.unlink()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)


def send(to: str, text: str, account: str | None = None) -> dict:
    if not HANDLE.match(to):
        raise Refused("the recipient must be +<country code><number> or an email address")
    if not text.strip() or len(text) > 65536 or "\0" in text:
        raise Refused("the text must be non-empty, at most 65,536 characters, with no NUL")
    guards, paths = core()
    try:
        config = paths.config()
    except (OSError, ValueError) as exc:
        raise Refused(f"the synthesis config is unreadable ({exc}); sending is blocked until it is fixed")
    key = hashlib.sha256(f"{to}\0{text}".encode("utf-8")).hexdigest()[:32]
    record_path = paths.state() / "imessage-sends" / f"{key}.json"
    if record_path.exists():
        earlier = json.loads(record_path.read_text(encoding="utf-8"))
        if earlier.get("status") != "not-sent":
            raise Refused(f"an attempt to send this text to {to} at {earlier.get('at')} ended {earlier.get('status')}. "
                          "Never resend: check the conversation in Messages. If the principal wants these words sent "
                          "again, they send them by hand.")
    route = resolve_route(to, account)
    reason = guards.check_send(TOOL, {"to": to, "text": text}, config)
    if reason:
        return {"status": "needs-approval" if "approve " in reason else "refused", "reason": reason}
    record = {"to": to, "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
              "at": datetime.now().astimezone().isoformat(timespec="seconds")}
    _save(record_path, {**record, "status": "uncertain", "reason": "the send call started; its outcome was not recorded"})
    result = transport(to, text, route, key)
    _save(record_path, {**record, **result})
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    parser.add_argument("--to", required=True, help="the recipient's handle: +<country code><number> or an email address")
    parser.add_argument("--text-file", required=True, help="UTF-8 file holding the exact approved text")
    parser.add_argument("--account", help="the iMessage account id, when more than one has a chat with the recipient")
    args = parser.parse_args(argv)
    try:
        result = send(args.to, Path(args.text_file).read_text(encoding="utf-8"), args.account)
    except (Refused, OSError, ValueError) as exc:
        result = {"status": "refused", "reason": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return {"dispatched": 0, "refused": 2, "needs-approval": 2}.get(result["status"], 3)


if __name__ == "__main__":
    sys.exit(main())
