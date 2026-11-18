"""Approvals that only the principal can grant, bound to the exact thing approved (R3.0-R3.2).

When a guard blocks a send or a deploy it files a request under a random six-character
code, so nobody can know the code before the request exists. The principal types
"approve <code>" (or several codes after the one word) and the UserPromptSubmit hook
records a grant for each. The agent runs as the same
OS user and can write that grant itself, or feed the hook a made-up prompt (M5,
2026-10-05), so a grant alone never lets a call through: the harness's own record of the
session must also hold that prompt, typed by the principal after the request was filed.
Tool output, hook text, compaction summaries and other sessions' messages never count.
A verified grant lets exactly one matching call through and expires.

Every record here is sealed (the guard's sandbox, the principal's rulings of 2026-11-15): only the hook writes the
approvals folder, and each harness's sandbox keeps every shell out of it. A shell files its requests beside its working
state, where they grant nothing until the principal types the code; the hook grants them, named as a shell's, and itself
applies what a typed code approves whose effect is a sealed record (EFFECTS). A process that cannot write the folder
spends nothing, and says why.
"""

from __future__ import annotations

import _thread
import contextlib
import hashlib
import json
import os
import re
import time
from pathlib import Path

from synthesis import paths

TTL_SECONDS = 15 * 60
ONE = r"\d[0-9a-f]{5}\b"  # the shape request() issues: no English word fits
GAP = "[ \\t\\u00a0\\u1680\\u2000-\\u200a\\u202f\\u205f\\u3000]"  # a space inside a line; a line break is not one
NOT = r"(?:n['’]t|\b(?:not|never|no|cannot|dont|cant|wont))"  # "don't approve ...": group 1 of CODE when it stands before
# The word, then on its own line the codes it approves, separated by spaces, commas or "and". The first thing that
# is not a code ends the list: "approve code <code>", the form hook text is rewritten to, approves nothing
# (hook._defuse), and neither does pasted context that opens the next line with a code. A negation before the
# word, across any space, line break or removed block, is part of the match so that it can be refused.
CODE = re.compile(rf"(?:({NOT})[\s/]+)?\bapprove{GAP}+({ONE}(?:(?:{GAP}*,{GAP}*(?:and{GAP}+)?|{GAP}+and{GAP}+|{GAP}+){ONE})*)",
                  re.IGNORECASE)
# A harness wraps what it inserts into a prompt in a pair of tags: a closing tag, or the start of an opening one.
TAG = re.compile(r"<(?:(/)([^\W\d][\w.:-]*)\s*>|([^\W\d][\w.:-]*)(?=[\s/>]))")
CUT = " / "  # stands where a wrapped block was: it ends a list and parts the word from a code
NOT_TYPED = ("isMeta", "isSidechain", "isCompactSummary", "isVisibleInTranscriptOnly", "isSynthetic", "toolUseResult")


class Unverified(PermissionError):
    """A grant exists, but the harness's record does not show the principal typing it."""


class Sealed(PermissionError):
    """This process cannot write the sealed approvals folder: a shell the harness's sandbox confines, which files
    requests and spends nothing."""


def _sealed(exc: OSError) -> Sealed:
    return Sealed(f"This process cannot write {paths.approvals()}, the sealed approvals folder ({exc.strerror or exc}): only the "
                  "hook spends or withdraws an approval, and a shell the sandbox confines files requests alone. Make the call the "
                  "approval is for, and the hook spends it there.")


IN_HOOK = False  # set by the hook process (hook.main): a request it files is sealed, anyone else's goes to state/requests
SHELL = " (a request a shell command filed, in its own words)"  # how a grant of one is named to the principal
# What a typed code approves whose effect is a sealed record: the hook applies it once the session's record shows the
# code typed (hook.apply_effects), since a shell can no longer write the record itself (design 2.3).
EFFECTS = frozenset({"disclosure-line", "send-window", "send-batch"})


def digest(kind: str, subject) -> str:
    canonical = subject if isinstance(subject, str) else json.dumps(subject, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{kind}\0{canonical}".encode("utf-8")).hexdigest()


def _dir(name: str) -> Path:
    return paths.approvals() / name


def _folders() -> tuple:
    """Where requests wait: the hook's, sealed, first, then those a shell filed."""
    return _dir("requests"), paths.requests()


def _request_file(code: str) -> Path:
    """The pending request of this code: the hook's where one is filed under it, else a shell's. A shell's under a code
    the hook filed is never granted: a shell can read the hook's codes and plant its own request under one."""
    sealed = _dir("requests") / f"{code}.json"
    return sealed if sealed.exists() else paths.requests() / f"{code}.json"


def how(code: str) -> str:
    """What the principal types, worded so that tool output or hook text repeating it never holds the phrase."""
    return f"approve followed by the code {code}"


def pending() -> list[str]:
    """The codes of requests waiting for the principal, the hook's and the shells'."""
    return list(dict.fromkeys(p.stem for folder in _folders() for p in folder.glob("*.json")))


def request(kind: str, subject, summary: str, carry: dict | None = None) -> str:
    """File (or refresh) a pending request; returns the code the principal types. A retry keeps the code the principal
    was already shown. Inside `one_code` the request joins the call's, filed together under one code when it ends. A
    request of a kind in EFFECTS carries its subject, and `carry` what else the hook needs to apply it."""
    entry = {"kind": kind, "digest": digest(kind, subject), "summary": summary,
             **({"subject": subject, **(carry or {})} if kind in EFFECTS else {})}
    if CALL:
        CALL[0]["entries"] += [] if any(e["digest"] == entry["digest"] for e in CALL[0]["entries"]) else [entry]
        CALL[0]["shown"] = CALL[0]["shown"] or _new_code()  # made on the first request: a call that asks none pays nothing
        return CALL[0]["shown"]
    return _file([entry], _new_code())


def _new_code() -> str:
    import secrets
    return str(secrets.randbelow(10)) + secrets.token_hex(3)[:5]  # a leading digit keeps every code apart from English words


def _file(entries: list, code: str) -> str:
    """File these requests under the code a pending request of exactly these already has (a retry), else under `code`.
    Never a code that carries anything else: a code the principal was shown names exactly what it grants (the
    integration review of 5.24.1, finding 1: a later call's requests joined a code shown for fewer). The hook files in
    the sealed folder; any other process beside its state, marked as a shell's, under a code the hook has not filed."""
    _expire()
    folder, keys = _dir("requests") if IN_HOOK else paths.requests(), sorted(e["digest"] for e in entries)
    code = next((p.stem for p in folder.glob("*.json") if sorted(_keys(p)) == keys), code)
    while not IN_HOOK and (_dir("requests") / f"{code}.json").exists():
        code = _new_code()
    paths.write_json(folder / f"{code}.json", {**entries[0], "at": time.time(), **({"also": entries[1:]} if entries[1:] else {}),
                                               **({} if IN_HOOK else {"by": "shell"})})
    return code


CALL: list = []  # while one call is judged (`one_code`): {"shown": the code its requests said, "entries": them, "code"}


@contextlib.contextmanager
def one_code():
    """Every request filed inside joins the call's, so a call several checks hold asks the principal once (A5,
    2026-11-17). They are filed when it ends, and `code` is then the one they share, which replaces the `shown` one in
    what the call says; a call judged inside another joins the outer one's."""
    if CALL:
        yield CALL[0]
        return
    call = {"shown": "", "entries": [], "code": ""}
    CALL.append(call)
    try:
        yield call
    finally:
        CALL.clear()
        call["code"] = _file(call["entries"], call["shown"]) if call["entries"] else ""


def _entries(data: dict) -> list:
    """The requests one code carries: the first, then those listed beside it."""
    also = data.get("also") if isinstance(data.get("also"), list) else []
    return [e for e in [data, *also] if isinstance(e, dict) and isinstance(e.get("digest"), str) and e.get("kind")]


def _keys(path: Path) -> list:
    return [e["digest"] for e in _entries(paths.read_json(path))]


def _expire() -> None:
    """Drop requests and grants older than the TTL, so state never grows (R8.3); a process that cannot write the sealed
    folder drops only the requests beside its state."""
    cutoff = time.time() - TTL_SECONDS
    for path in (p for folder in (*_folders(), _dir("grants"), _dir("effects")) for p in folder.glob("*.json")):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except (FileNotFoundError, PermissionError):
            pass


def typed_text(prompt: str) -> str:
    """The prompt without the blocks a harness wrapped into it, such as a background task's report (2026-10-20: a
    helper's report quoting the guard reached this hook as a prompt). What a wrapper holds can carry the wrapper's
    own closing tag (in a comment, a quoted report, on purpose), so no pairing of tags says where a block ends:
    everything from a name's first opening tag to its last closing tag goes, and a mark stands where it was so no
    list runs across it. One pass over the tags, so a long prompt cannot stall the hook (2026-11-11: removing
    blocks one pattern match at a time took seconds on 300,000 characters)."""
    prompt, first, last = prompt or "", {}, {}
    for tag in TAG.finditer(prompt):
        if tag[3]:
            first.setdefault(tag[3].lower(), tag.start())
        elif tag[2].lower() in first:
            last[tag[2].lower()] = tag.end()
    kept, at = [], 0
    for start, end in sorted((first[name], end) for name, end in last.items()):
        if start >= at:
            kept.append(prompt[at:start])
        at = max(at, end)
    return CUT.join(kept + [prompt[at:]])


def typed_codes(prompt: str) -> list[str]:
    """The codes the principal approved in what they typed. One "approve" may carry several (2026-11-11: nine were
    typed after the word and eight were passed over). A negation before the word approves nothing."""
    lists = [m[2] for m in CODE.finditer(typed_text(prompt)) if not m[1]]
    return list(dict.fromkeys(code.lower() for codes in lists for code in re.findall(ONE, codes, re.IGNORECASE)))


def mentioned(prompt: str) -> list[str]:
    """Every word shaped like a code anywhere in the message, tags and wrapped blocks included: it grants nothing,
    and it lets the hook name a pending code that was in the message and did not take."""
    return list(dict.fromkeys(code.lower() for code in re.findall(rf"\b{ONE}", prompt or "", re.IGNORECASE)))


def grant_from_prompt(prompt: str, transcript_path: str = "", session_id: str = "") -> list[str]:
    """Grant every pending request whose code the prompt carries, each with where the session's record ended when the
    principal typed, so that finding his prompt reads only from there, and the session it was typed in. A request of a
    kind in EFFECTS waits in effects/ for the hook to apply it. Returns the summaries granted, a shell's named as one."""
    said, me = [], session_id or paths.session_id()
    try:
        ended = {"record_at": os.path.getsize(transcript_path)} if transcript_path and os.path.isfile(transcript_path) else {}
    except OSError:
        ended = {}
    for code in typed_codes(prompt):
        pending_file = _request_file(code)
        data, shell = paths.read_json(pending_file), pending_file.parent == paths.requests()
        for entry in _entries(data) if data.get("digest") else []:  # every request the code carries (A5)
            effect = entry["kind"] in EFFECTS and digest(entry["kind"], entry.get("subject")) == entry["digest"]
            paths.write_json(_dir("effects" if effect else "grants") / f"{entry['digest']}.json", {
                **(entry if effect else {}), "kind": entry["kind"], "digest": entry["digest"], "summary": entry.get("summary", ""),
                "code": code, "asked": data.get("at", 0), "at": time.time(), "session": me, "shell": shell, **ended})
            said.append(entry.get("summary", "") + SHELL * shell)
        for folder in _folders():  # a shell's request planted under the hook's code goes with it
            (folder / f"{code}.json").unlink(missing_ok=True)
    return said


def transcript(session: dict | None) -> str:
    """The harness's record of this session: the hook payload's transcript_path, else the path the prompt hook recorded
    for this session's id in the state folder, where it lies inside the folders recorded beside it. Never one found
    through folders the caller's environment names, which an agent's own command sets (review of 5.22.1, finding 13;
    round 4 of 5.23.1's approval fix, finding 1: a program pointed the path at a record it wrote, and a script's own
    check read the principal's prompt there). A session no prompt of the principal's reached has none."""
    given = str((session or {}).get("transcript_path") or "")
    sid = paths.session_id(session)
    if given or not re.fullmatch(r"[\w.-]+", sid):
        return given
    record = paths.read_json(_dir("records") / f"{sid}.json")
    recorded = str(record.get("path") or "")
    folders = record["folders"] if "folders" in record else _account_folders()  # a note 5.23's prompt hook wrote names none
    return recorded if os.path.isfile(recorded) and _kept_by_a_harness(recorded, folders) else ""


def _account_folders() -> dict:
    """Each harness's folders under the account's own home, where a note 5.23's prompt hook wrote may lie (A9); none for an
    account the user database does not know (the integration review of 5.24.1)."""
    try:
        home = paths.account_home()
    except KeyError:
        return {}
    return {"claude-code": home / ".claude" / "projects", "codex": home / ".codex" / "sessions", "codex-archived": home /
            ".codex" / "archived_sessions", "muse": home / ".local" / "share" / "muse" / "sessions",
            "desktop": home / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions"}


def remember(session_id: str, transcript_path: str) -> None:
    """Record where the harness keeps a session's transcript, as its prompt hook names it, for a command that session
    runs, with the folders each harness keeps its records in as this process's environment names them. The prompt hook
    records them: the harness starts it, with the harness's own environment, which no agent's command sets, while a
    check a script enters runs inside the agent's command, which can name any folder as a harness's for itself. The
    sealed approvals folder holds them, which only the hook writes."""
    if re.fullmatch(r"[\w.-]+", str(session_id or "")) and transcript_path and os.path.isabs(str(transcript_path)):
        record = {"path": str(transcript_path), "folders": {**{name: str(root) for name, root in paths.transcript_roots().items()},
                                                            "codex-archived": str(paths.codex_home() / "archived_sessions"),  # as sessions.natives reads them
                                                            "desktop": str(paths.desktop_dir() / "local-agent-mode-sessions")}}
        if paths.read_json(_dir("records") / f"{session_id}.json") != record:
            paths.write_json(_dir("records") / f"{session_id}.json", record)


def _kept_by_a_harness(path: str, folders) -> bool:
    """Whether a path, where it really leads, lies inside one of the folders the prompt hook recorded: a harness's own,
    or, under the desktop app's, an agent-mode session's records (`<account>/<org>/local_<session>/.claude/projects`),
    never another file of that session. A note 5.23's prompt hook wrote names none: `transcript` reads it against each
    harness's folders under the account's own home, which no variable a command sets can move (A9)."""
    real = os.path.realpath(path)
    for name, root in folders.items() if isinstance(folders, dict) else ():
        base = os.path.realpath(str(root))
        below = os.path.relpath(paths.spelled(real), paths.spelled(base)).split(os.sep) if paths.inside(real, base) and real != base else []
        if below and (name != "desktop" or (len(below) > 5 and below[2].startswith("local_") and below[3:5] == [".claude", "projects"])):
            return True
    return False


def _prompt(record: dict, session_id: str) -> tuple[float, list]:
    """(time, its blocks of text) when a transcript line is a prompt the principal typed, else (0, []).
    Claude Code: a user entry, or a prompt typed while the agent worked, from a human; never meta, a
    subagent's, a compaction summary or a tool result. Codex: the user's own message item, never a tool
    output or a hook's prompt. Muse: a chat intent accepted on this session's main surface. Each block is
    read by itself, and a block marked as not the principal's is left out as a whole record would be."""
    body = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    item, queued = body.get("item") or {}, record.get("attachment") or {}
    if record.get("type") == "user":
        entry, content = record, (record.get("message") or {}).get("content")
    elif record.get("type") == "attachment" and queued.get("type") == "queued_command" and queued.get("commandMode") == "prompt":
        entry, content = queued, queued.get("prompt")
    elif record.get("type") == "event_msg" and (body.get("type") == "user_message" or item.get("type") == "UserMessage"):
        entry, content = record, body.get("message") if body.get("type") == "user_message" else item.get("content")
    elif (record.get("payload_type") == "runtime.user_intent.accepted" and body.get("surface") == "main"
          and (body.get("semantic_kind") or {}).get("kind") == "chat" and body.get("source_session_id") in (None, session_id)):
        entry, content = record, body.get("refill_blocks")
    else:
        return 0.0, []
    blocks = [{"text": b} if isinstance(b, str) else b for b in (content if isinstance(content, list) else [content])]
    blocks = [b for b in blocks if isinstance(b, dict)]

    def machine(part: dict) -> bool:
        origin = part.get("origin")
        return any(part.get(k) for k in NOT_TYPED) or (isinstance(origin, dict) and origin.get("kind") != "human")
    if machine(entry) or any(b.get("type") == "tool_result" for b in blocks):
        return 0.0, []
    texts = [str(b.get("text") or "") for b in blocks if not machine(b)]
    stamp = record.get("timestamp") or record.get("recorded_at")
    if isinstance(stamp, (int, float)):
        return stamp / 1e6, texts  # Muse records microseconds
    from datetime import datetime
    return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp(), texts


STAMP = re.compile(r'"(?:timestamp|recorded_at)"\s*:\s*(?:"([^"]{10,40})"|(\d{10,19}))')
OLD_RUN, SLACK_SECONDS = 200, 600  # with no position: this many lines in a row, older than the window by this much, end it
MARGIN = 16 << 20  # read this far before the position the grant records: the prompt line may be written before the hook runs


def _stamps(line: str) -> list:
    """Every time a record line carries, as seconds, nested ones included: ISO times, and numbers read by their length
    (seconds, milliseconds, Muse's microseconds, nanoseconds)."""
    from datetime import datetime
    found = []
    for iso, number in STAMP.findall(line):
        try:
            found.append(int(number) / 10 ** (3 * min(3, max(0, (len(number) - 9) // 3))) if number
                         else datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())
        except (ValueError, OverflowError):
            continue
    return found


def _lines_back(transcript_path: str, block: int = 1 << 20, stop: int = 0):
    """A record's lines from its end back to the line that holds the byte `stop`, newest first, that line whole even when
    it began before `stop` (review round 2 of the spend order, finding 3: a prompt line longer than the margin was cut).
    A line longer than a block is kept as its pieces and joined once, so reading it costs its length, not its square."""
    with open(transcript_path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        at, tail = handle.tell(), []  # tail: the pieces of the line being read backward, the latest piece first
        while at > stop:
            step = min(block, at - stop)
            at -= step
            handle.seek(at)
            data = handle.read(step)
            if b"\n" not in data:
                tail.append(data)
                continue
            lines = data.split(b"\n")
            newest = lines[-1] + b"".join(reversed(tail))
            if newest.strip():
                yield newest.decode("utf-8", "replace")
            for raw in reversed(lines[1:-1]):
                if raw.strip():
                    yield raw.decode("utf-8", "replace")
            tail = [lines[0]]
        while 0 < at <= stop:  # the line holding `stop` may have begun before it: read back to its start
            step = min(block, at)
            at -= step
            handle.seek(at)
            data = handle.read(step)
            cut = data.rfind(b"\n")
            tail.append(data[cut + 1:])
            if cut >= 0:
                break
        rest = b"".join(reversed(tail))
        if rest.strip():
            yield rest.decode("utf-8", "replace")


def typed(transcript_path: str, code: str, since: float, session_id: str = "", start=None) -> bool:
    """Whether the harness's record shows the principal typing approve <code> after `since` (`showing`)."""
    return showing(transcript_path, code, since, session_id, start) is not None


def showing(transcript_path: str, code: str, since: float, session_id: str = "", start=None) -> tuple | None:
    """(when, the SHA-256 of its line) of the prompt in the harness's record that shows the principal typing approve
    <code> after `since`; None for none. The record is read from its end:
    back to MARGIN before `start`, where the record ended when the prompt hook granted, and the whole line there (a
    forged position can only hide a prompt, never add one), and with no position, only as far as the approval window, a run of lines all older than it
    ending the search (2026-11-15: a Codex record of 1.9 GB took 4.6 s to read from its start, past the hook's 4 s; then
    a compaction block of older lines written after a prompt ended the window's search before it)."""
    if not code:
        return None
    size = os.path.getsize(transcript_path)
    bounded = isinstance(start, int) and not isinstance(start, bool) and 0 <= start <= size
    hit, old = re.compile(re.escape(code), re.IGNORECASE), 0
    for line in _lines_back(transcript_path, stop=max(0, start - MARGIN) if bounded else 0):
        if hit.search(line):
            try:
                when, texts = _prompt(json.loads(line), session_id)
            except (ValueError, TypeError, AttributeError):
                when, texts = 0.0, []
            if when > since and any(code in typed_codes(text) for text in texts):
                return when, hashlib.sha256(line.encode("utf-8", "replace")).hexdigest()
        stamps = [] if bounded else _stamps(line)
        if stamps:
            old = old + 1 if max(stamps) < since - SLACK_SECONDS else 0
            if old >= OLD_RUN:
                return None
    return None


def grant(kind: str, subject) -> dict:
    """The live grant of exactly this subject as recorded (its code, and when it was asked for); {} for none. Spends
    nothing: a batch keeps its code, so each of its sends can find the principal typing it again."""
    return paths.read_json(_dir("grants") / f"{digest(kind, subject)}.json")


def _muse(session: dict | None) -> bool:
    """A Muse session gets no approval until Muse's sandbox is shown to keep its shells out of the sealed folders (the
    principal's ruling of 2026-11-15): a grant typed elsewhere, or there, lets nothing through in one."""
    return paths.harness(session) == "muse"


def granted(kind: str, subject, session: dict | None = None, why: list | None = None) -> bool:
    """A live grant of exactly this subject that the principal's own prompt backs. Spends nothing, so a shell may ask it:
    it holds until it expires, for an approval of a thing (an address, an accepted loss, a review) that is the same
    whenever it is read, or that each call it lets through still waits on on its own. With `why`, a grant there that the
    record does not back adds the reason to it."""
    data = paths.read_json(_dir("grants") / f"{digest(kind, subject)}.json")
    if data.get("kind") != kind or time.time() - float(data.get("at", 0)) > TTL_SECONDS or _muse(session):
        return False
    shown, _, problem = _backing(data, session)
    if why is not None and not shown:
        why.append(problem)
    return bool(shown)


def answered(kind: str, subject, session: dict | None = None) -> bool:
    """True once where the session's own record shows the principal typing the code of the request for exactly this
    subject after it was filed, though no prompt hook made a grant of it: a command that checks its own approval (the
    CLI's install and uninstall) reads that record itself, so a runtime can be approved while none runs the hook. The
    request is spent."""
    key, record = digest(kind, subject), transcript(session)
    for code in pending() if record and not _muse(session) else []:
        file = _request_file(code)
        data = paths.read_json(file)
        if key not in [e["digest"] for e in _entries(data)] or time.time() - float(data.get("at", 0)) > TTL_SECONDS:
            continue
        try:
            if typed(record, code, float(data.get("at", 0)), paths.session_id(session)):
                rest = [e for e in _entries(data) if e["digest"] != key]  # the code's other requests stay for their own checks
                if rest:
                    paths.write_json(file, {**rest[0], "at": data.get("at", 0), "also": rest[1:]})
                else:
                    file.unlink(missing_ok=True)
                return True
        except PermissionError as exc:
            raise _sealed(exc) from None
        except OSError:
            return False
    return False


def void(kind: str, subject) -> list:
    """Spend a grant of exactly this subject, and drop a request for one that still waits, using neither: the same
    thing went out on another code, so a second copy has to be shown again (2026-11-13: a message released by the
    code for a time in its words left the ordinary grant live, and an identical call went a second time on it).
    Returns what it removed, (file, bytes) each, for a call that is then held to put back. A request carried beside
    others takes its code with it: that code was shown granting it (the integration review of 5.24.1)."""
    key = digest(kind, subject)
    files = [_dir("grants") / f"{key}.json"] + [p for folder in _folders() for p in folder.glob("*.json") if key in _keys(p)]
    removed = []
    for path in files:
        try:
            held = path.read_bytes()
            path.unlink()
        except FileNotFoundError:
            continue
        except PermissionError as exc:
            raise _sealed(exc) from None
        removed.append((path, held))
    return removed


@contextlib.contextmanager
def alone():
    """One decision at a time for a thing that can go on either of two codes: the code that lets it go spends the
    other before an identical call, judged at the same moment, is looked at (2026-11-13, a review: between the two
    steps a second copy went on the other code). Taken again inside itself by the thread that holds it, it does not
    lock again: the lock belongs to the open file, so a second one would wait for good (review round 4, finding 5);
    another thread waits for it like another process (round 5, finding 2)."""
    me = _thread.get_ident()
    if _ALONE[0] and _ALONE[1] == me:
        _ALONE[0] += 1
        try:
            yield
        finally:
            _ALONE[0] -= 1
        return
    import fcntl
    held = _dir("lock")  # beside the folders: a spent or expired approval leaves no file in them
    try:
        held.parent.mkdir(parents=True, exist_ok=True)
        handle = open(held, "a")
    except PermissionError as exc:
        raise _sealed(exc) from None
    with handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        _ALONE[0], _ALONE[1] = 1, me
        try:
            yield
        finally:
            _ALONE[0], _ALONE[1] = 0, None


_ALONE = [0, None]  # how many times the thread `_ALONE[1]` holds the lock of `alone`


SPENT: list = []  # (grant file, the bytes it held) each grant this call used, for the hook to give back if the call is held


def put_back(items: list) -> None:
    """Put each (file, bytes) back whole, never over a file now in its place: written beside it first, then linked in,
    so an identical call never finds it half written (review round 2 of the spend order, finding 2)."""
    for path, data in items:
        made = Path(path).with_name(f".{Path(path).name}.{os.getpid()}.back")
        try:
            handle = os.open(made, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError:
            continue  # the folder is gone, or another put-back of it is under way
        try:
            try:
                view = memoryview(data)
                while view:  # a write may take only part
                    view = view[os.write(handle, view):]
            finally:
                os.close(handle)
            os.link(made, path)
        except OSError:
            pass  # a newer file of the same thing is in place: nothing to put back
        finally:
            made.unlink(missing_ok=True)


def _spend(path: Path) -> bytes | None:
    """Take a grant once: the bytes it held, or None where another caller took it first."""
    spent = path.with_suffix(".spent")
    try:
        os.replace(path, spent)
    except FileNotFoundError:
        return None
    except PermissionError as exc:
        raise _sealed(exc) from None
    try:
        return spent.read_bytes()
    except OSError:
        return b""
    finally:
        spent.unlink(missing_ok=True)


def consume(kind: str, subject, session: dict | None = None) -> bool:
    """True once for a live grant of exactly this subject that the principal's own prompt backs. The
    grant is read before it is spent, so a deadline that ends the read leaves it for the identical retry (2026-11-15:
    two grants were spent, then the read ran past the hook's 4 s); a grant that does not hold, or that the record does
    not back, is spent all the same, and for the latter the request is filed again and this raises."""
    path = _dir("grants") / f"{digest(kind, subject)}.json"
    try:
        before = path.read_bytes()
    except FileNotFoundError:
        return False
    if _muse(session):
        return False
    try:
        data = json.loads(before)
    except ValueError:
        data = {}
    data = data if isinstance(data, dict) else {}
    if data.get("kind") != kind or time.time() - float(data.get("at", 0)) > TTL_SECONDS:
        _spend(path)
        return False
    shown, record, problem = _backing(data, session)
    if shown:
        if _spend(path) != before:  # once; a grant put in place while the record was read was never checked
            return False
        SPENT.append((path, before))
        _ledger(data, record, shown)
        return True
    _spend(path)
    raise Unverified(unbacked(problem, request(kind, subject, str(data.get("summary", "")))))


def _backing(data: dict, session: dict | None) -> tuple:
    """(where the session's own record shows the principal typing this grant's code since it was asked for, or None;
    the record; why it does not, or '')."""
    record, since = transcript(session), max(float(data.get("asked", 0)), time.time() - TTL_SECONDS)
    try:
        shown = showing(record, str(data.get("code", "")), since, paths.session_id(session), data.get("record_at")) if record else None
    except OSError as exc:
        return None, record, f"the session's transcript could not be read ({exc})"
    return shown, record, "" if shown else (f"{record} shows no prompt from the principal with its code since it was asked for"
                                            if record else "the harness gave no transcript for this session, and only that "
                                            "record can show who typed it")


def unbacked(problem: str, code: str) -> str:
    return (f"An approval for this call was recorded, but {problem}. Approvals come only from the principal's own prompt, "
            f"so it was not used. Show them the exact call again and ask them to type {how(code)}.")


def _ledger(data: dict, record: str, shown: tuple) -> None:
    """One line in granted.jsonl for each typed code the hook spends: the code, what it granted, when the principal typed
    it, and the record and line that showed it."""
    row = {"code": data.get("code"), "kind": data.get("kind"), "digest": data.get("digest"), "summary": data.get("summary"),
           "typed": shown[0], "record": record, "line": shown[1], "at": time.time(), **({"shell": True} if data.get("shell") else {})}
    with open(_dir("granted.jsonl"), "a", encoding="utf-8") as log:
        log.write(json.dumps(row, ensure_ascii=False) + "\n")


def ready(session: dict | None) -> list:
    """(file, grant, (when, line)) for each grant waiting in effects/ that this session's own record shows the principal
    typing, oldest first: the hook applies each (hook.apply_effects). Nothing in a Muse session."""
    found, me = [], paths.session_id(session)
    waiting = sorted(_dir("effects").glob("*.json"), key=lambda p: p.stat().st_mtime) if _dir("effects").is_dir() else []
    record = transcript(session) if waiting and not _muse(session) else ""
    for path in waiting if record else []:
        data = paths.read_json(path)
        if (data.get("session") != me or data.get("kind") not in EFFECTS or time.time() - float(data.get("at", 0)) > TTL_SECONDS
                or digest(data["kind"], data.get("subject")) != path.stem):
            continue
        try:
            shown = showing(record, str(data.get("code", "")), max(float(data.get("asked", 0)), time.time() - TTL_SECONDS), me,
                            data.get("record_at"))
        except OSError:
            continue
        found += [(path, data, shown)] if shown else []
    return found


def apply(path: Path, data: dict, shown: tuple, record: str, effect) -> str:
    """Spend one waiting effect grant and apply it (`effect(data)`, what it says it did); one another hook took first is
    left alone, and one whose effect fails is put back for the next hook event to try again."""
    before = _spend(path)
    if before is None:
        return ""
    try:
        said = effect(data)
    except BaseException:  # a deadline too: the grant stays for the next hook event
        put_back([(path, before)])
        raise
    _ledger(data, record, shown)
    return said
