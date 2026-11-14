# SPDX-License-Identifier: Apache-2.0
"""Send one approved message to an existing Messages chat through the v5 send guard, at most once.

Run: python3 messages_send.py --to HANDLE --text-file FILE [--photo PATH] [--account ACCOUNT_ID]
     python3 messages_send.py --members HANDLE[,HANDLE...] --text-file FILE [--photo PATH] [--service iMessage|SMS]
                              [--account ID]

--photo adds one photo (2026-10-22, the principal's ruling: iMessage and SMS photos send directly). The approval
names it by SHA-256 along with the text, the photo goes first and the text after it as its caption, and the text
may be left out for a photo alone.

--to reaches the one-to-one iMessage chat with HANDLE. --members reaches the one existing chat, iMessage or SMS,
group or one-to-one, whose members are exactly those handles (2026-10-20: a trip's SMS group); the approval names
every member, and the send stops if the chat's members or service changed since.

1. An earlier attempt with this recipient and text refuses the send, unless that attempt is
   known not to have reached the send call: never resend after an uncertain outcome.
2. The one existing chat is found read-only (messages_route.js). No chat is created, a chat's service is never
   changed (no fallback between iMessage and SMS), and RCS is never used.
3. The v5 send guard decides: the principal's forbidden phrases, then their single-use approval
   of this exact recipient and text. Without one it files a request and prints the code the
   principal types ("approve <code>"); after they do, run the identical command again.
4. The attempt is recorded, then one send call per part (the photo, then the text) runs through
   messages_transport.js. The text travels through a private file descriptor, never through argv or script
   source; the transport sends the photo only if its size and change time still match the approved one.

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
TOOL, MEMBERS_TOOL = "imessage_send", "messages_send"
KEEP_SECONDS = 30 * 86400
# Errors messages_transport.js throws before its one send call, so nothing can have been sent.
PRE_SEND = ("descriptor required", "descriptor bound", "packet contract", "payload contract",
            "explicit route required", "text bound", "route bound", "recipient contract",
            "approval expired or unbounded", "selection bound", "ambiguous route", "account unavailable",
            "chat account changed", "one recipient required", "participant route changed", "members contract",
            "participants changed", "attachment bound", "attachment changed")
# A photo is approved by its content: SHA-256, name and size go into the approval along with the text.
PHOTO_TYPES = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".gif", ".webp")
PHOTO_MAX = 100 * 1024 * 1024


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


def resolve_members(members: list, service: str | None, account: str | None) -> dict:
    try:
        done = osascript(HERE / "messages_route.js", ["members", json.dumps(members)])
    except OSError as exc:
        raise Refused(f"cannot run osascript: {exc}") from exc
    if done is None or done.returncode:
        raise Refused("could not read the Messages accounts and chats: " + ("timed out" if done is None else done.stderr.strip()[-500:]))
    usable = [r for r in json.loads(done.stdout)["routes"] if r["usable"] and (not account or r["account_id"] == account)
              and (not service or r["service"] == service)]
    if not usable:
        raise Refused(f"no existing chat whose members are exactly {', '.join(members)} on a connected iMessage or SMS "
                      "account. Start it in Messages first; this tool never creates a chat or changes its service.")
    if len(usable) > 1:
        raise Refused("several chats have exactly these members; pass --service and --account to choose one of: "
                      + "; ".join(sorted(f"{r['service']} on {r['account_id']}" for r in usable)))
    chosen = usable[0]
    return {k: chosen[k] for k in ("account_id", "service", "chat_id", "participants")}


def photo(path: str | None) -> dict | None:
    """The photo as approved: its real path, name, size, change time and SHA-256, read once."""
    if path is None:
        return None
    real = Path(path).expanduser().resolve()
    if real.suffix.lower() not in PHOTO_TYPES:
        raise Refused(f"a photo must be one of {', '.join(PHOTO_TYPES)}; got {real.name}")
    try:
        info, digest = real.stat(), hashlib.sha256()
        if not real.is_file() or not 0 < info.st_size <= PHOTO_MAX:
            raise Refused(f"the photo must be a file of at most {PHOTO_MAX >> 20} MB")
        with open(real, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
    except OSError as exc:
        raise Refused(f"cannot read the photo: {exc}") from exc
    return {"path": str(real), "name": real.name, "bytes": info.st_size, "mtime": info.st_mtime_ns / 1e9,
            "sha256": digest.hexdigest()}


def transport(to, text: str, route: dict, key: str, attachment: dict | None = None) -> dict:
    sent = {k: attachment[k] for k in ("path", "bytes", "mtime")} if attachment else None
    payload = {"tool_name": "synthesis.messages.send",
               "tool_input": {"request_id": key, "destination": to, "text": text, "route": route, "attachment": sent}}
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
        if reply.get("request_digest") == packet["digest"] and reply.get("phase") == "dispatched":
            return {"status": "dispatched", "parts": reply.get("parts"), "delivery": "unknown", "acknowledgement": "unknown"}
        if reply.get("request_digest") == packet["digest"] and reply.get("phase") == "partial":
            return {"status": "uncertain", "reason": f"the photo's send call returned, then the text's failed: {reply.get('error')}"}
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


def _send(to, text: str, key: str, resolve, tool: str, subject, attachment: dict | None = None) -> dict:
    """The shared path: refuse a repeat, find the chat, ask the guard, record, then one send call per part."""
    if (not text.strip() and attachment is None) or len(text) > 65536 or "\0" in text:
        raise Refused("the text must be non-empty unless a photo goes alone, at most 65,536 characters, with no NUL")
    guards, paths = core()
    try:
        config = paths.config()
    except (OSError, ValueError) as exc:
        raise Refused(f"the synthesis config is unreadable ({exc}); sending is blocked until it is fixed")
    record_path = paths.state() / "imessage-sends" / f"{key}.json"
    if record_path.exists():
        earlier = json.loads(record_path.read_text(encoding="utf-8"))
        if earlier.get("status") != "not-sent":
            shown = to if isinstance(to, str) else ", ".join(to)
            raise Refused(f"an attempt to send this text to {shown} at {earlier.get('at')} ended {earlier.get('status')}. "
                          "Never resend: check the conversation in Messages. If the principal wants these words sent "
                          "again, they send them by hand.")
    route = resolve()
    reason = guards.check_send(tool, subject(route), config)
    if reason:
        return {"status": "needs-approval" if "approve " in reason else "refused", "reason": reason}
    record = {"to": to, "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
              "at": datetime.now().astimezone().isoformat(timespec="seconds")}
    if attachment:
        record["photo_sha256"] = attachment["sha256"]
    _save(record_path, {**record, "status": "uncertain", "reason": "the send call started; its outcome was not recorded"})
    result = transport(to, text, route, key, attachment)
    _save(record_path, {**record, **result})
    return result


def _named(attachment: dict | None) -> dict:
    """What the approval names about a photo: the principal sees its name and size, and the hash binds its bytes."""
    return {"photo": {k: attachment[k] for k in ("name", "bytes", "sha256")}} if attachment else {}


def _key(*parts: str, attachment: dict | None = None) -> str:
    """A text-only send keeps the key it had before photos, so its earlier attempts still refuse a repeat."""
    return hashlib.sha256("\0".join(parts + ((attachment["sha256"],) if attachment else ())).encode("utf-8")).hexdigest()[:32]


def send(to: str, text: str, account: str | None = None, attachment: dict | None = None) -> dict:
    if not HANDLE.match(to):
        raise Refused("the recipient must be +<country code><number> or an email address")
    return _send(to, text, _key(to, text, attachment=attachment), lambda: resolve_route(to, account), TOOL,
                 lambda route: {"to": to, "text": text, **_named(attachment)}, attachment)


def send_members(members: list, text: str, service: str | None = None, account: str | None = None,
                 attachment: dict | None = None) -> dict:
    """The approval binds every member, the chat's service and the chat itself, so it covers exactly this send."""
    members = sorted(set(members))
    if not 1 <= len(members) <= 32 or not all(HANDLE.match(m) for m in members):
        raise Refused("members must be 1 to 32 handles, each +<country code><number> or an email address")
    if service not in (None, "iMessage", "SMS"):
        raise Refused("the service must be iMessage or SMS")
    key = _key("members", ",".join(members), text, attachment=attachment)
    return _send(members, text, key, lambda: resolve_members(members, service, account), MEMBERS_TOOL,
                 lambda route: {"to": members, "service": route["service"], "text": text, "chat": route["chat_id"],
                                **_named(attachment)}, attachment)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--to", help="the recipient's handle: +<country code><number> or an email address")
    target.add_argument("--members", help="comma-separated handles: exactly the members of an existing chat")
    parser.add_argument("--text-file", help="UTF-8 file holding the exact approved text (with --photo, its caption)")
    parser.add_argument("--photo", help="one photo to send first, approved by its SHA-256 with the text")
    parser.add_argument("--service", choices=("iMessage", "SMS"), help="with --members, when chats on both match")
    parser.add_argument("--account", help="the Messages account id, when more than one has a matching chat")
    args = parser.parse_args(argv)
    try:
        if not args.text_file and not args.photo:
            raise Refused("pass --text-file, --photo, or both")
        text = Path(args.text_file).read_text(encoding="utf-8") if args.text_file else ""
        picture = photo(args.photo)
        if args.members:
            result = send_members([m.strip() for m in args.members.split(",") if m.strip()], text, args.service,
                                  args.account, picture)
        elif args.service:
            raise Refused("--service goes with --members; --to reaches a one-to-one iMessage chat")
        else:
            result = send(args.to, text, args.account, picture)
    except (Refused, OSError, ValueError) as exc:
        result = {"status": "refused", "reason": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return {"dispatched": 0, "refused": 2, "needs-approval": 2}.get(result["status"], 3)


if __name__ == "__main__":
    sys.exit(main())
