"""Agent session transcripts, kept in one plain form for every harness (R1.3, R1.4, R9.2).

Claude Code, Codex and Muse each keep a session's record in their own folder and format. Claude Code deletes its
copies after `cleanupPeriodDays` (30 by default), Codex is moving its rollouts into a database, and Muse keeps an event
log, so the only full record of what was asked, decided and done can disappear or change shape. `export` copies each
session, incrementally, into <home>/sessions/<workspace>/<YYYY-MM>/<harness>-<session>/ as one JSON record per event:
the principal's prompts, replies, reasoning, tool calls and results, compactions, the models that answered. Secrets are
masked with the commit check's credential patterns, images are kept once as files named by their hash, and text a
harness repeats every turn is kept once. A native file is read only past the offset already exported. Nothing here
runs in a hook (R8.3): resume, handoff, checkpoints and the rituals call it.
"""

from __future__ import annotations

import base64
import collections
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from synthesis import paths

SEGMENT_BYTES = 8_000_000  # a closed segment never changes, so a repository holding them stores each once
# Records keep the whole conversation (prompts, replies, reasoning, compactions); a tool's input or output, or injected
# text, longer than BLOB_CHARS keeps its first HEAD_CHARS in the record and the whole text once per workspace in
# blobs/<sha256>.txt. Measured over 14 days of this Mac's sessions (2026-10-30): injected text 38% and tool output 38%
# of the export, the conversation 5%, much of it repeated across sessions.
BLOB_CHARS, HEAD_CHARS = 2000, 1000
BLOB_KINDS = ("tool_result", "tool_call", "system")
GLOB = set("*?[")
INJECTED = ("<system-reminder>", "<command-", "<local-command-", "<task-notification>", "<ci-monitor-event>",
            "<environment_context>", "<user_instructions>", "# AGENTS.md instructions", "<permissions instructions>")
MIME = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp", "application/pdf": "pdf"}
# Claude Code rows that only repeat or instrument what other rows hold: request copies, file backups, sync markers.
CLAUDE_SKIP = {"api-request", "api-request-blob", "api-request-shape", "file-history-snapshot", "file-history-delta",
               "bridge-session", "atis-latch", "last-prompt", "artifact-comment-monitor", "artifact-autoreact-ledger"}
ACTIVE_PROJECT = re.compile(r"Active project: ([A-Za-z0-9][A-Za-z0-9._-]*)")


def root() -> Path:
    return paths.sessions()


_SECRETS: list = []


def mask(text: str) -> str:
    """Every credential the commit check knows, a private key block and a bearer token, replaced by its kind and
    a hash prefix, so two copies of one secret can still be matched without either being readable."""
    if not _SECRETS:
        from synthesis import commit_check
        _SECRETS.extend((name, re.compile(rx)) for name, rx in commit_check.CREDENTIALS.items())
        _SECRETS.append(("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----[\s\S]{40,}?"
                                                   r"-----END [A-Z ]*PRIVATE KEY(?: BLOCK)?-----")))
        _SECRETS.append(("bearer token", re.compile(r"(?i)(?<=bearer )[A-Za-z0-9._~+/-]{20,}=*")))
    for name, rx in _SECRETS:
        text = rx.sub(lambda m: f"[redacted {name} {hashlib.sha256(m.group(0).encode('utf-8')).hexdigest()[:12]}]", text)
    return text


def _clean(value):
    if isinstance(value, str):
        return mask(value)
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    return value


def _injected(text: str) -> bool:
    return text.lstrip().startswith(INJECTED)


def workspace_of(cwd: str) -> str:
    """The name of the workspace folder (config `workspace_roots`, default ~/workspaces/*) that holds cwd."""
    here = os.path.realpath(os.path.expanduser(cwd or "~"))
    for pattern in paths.config().get("workspace_roots") or ["~/workspaces/*"]:
        base = Path(os.path.expanduser(pattern))
        for folder in base.parent.glob(base.name) if GLOB & set(base.name) else [base]:
            if folder.is_dir() and paths.inside(here, os.path.realpath(folder)):
                return folder.name
    return "other"


def _iso(value) -> str:
    """ISO-8601 UTC from an ISO string, or from epoch seconds, milliseconds or microseconds."""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and value:
        seconds = value / 1e6 if value > 1e14 else value / 1e3 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, timezone.utc).isoformat().replace("+00:00", "Z")
    return ""


class _Session:
    """One native transcript's export state: where its records go, what was already read and kept."""

    def __init__(self, harness: str, native: Path, session: str):
        self.harness, self.native, self.session = harness, native, session
        self.file = root() / ".state" / f"{harness}-{re.sub(r'[^A-Za-z0-9._-]', '_', session)}.json"
        s = paths.read_json(self.file)
        self.offset, self.seq, self.segment = s.get("offset", 0), s.get("seq", 0), s.get("segment", 1)
        self.folder = Path(s["folder"]) if s.get("folder") else None
        self.seen, self.meta = set(s.get("seen", [])), s.get("meta", {})
        self.model, self.last_user, self.lines = s.get("model", ""), s.get("last_user", ""), []
        self.skipped = collections.Counter(self.meta.get("skipped", {}))

    def once(self, rec: dict):
        """A record whose content was already kept for this session is counted, not kept again."""
        key = hashlib.sha256(json.dumps([rec.get("kind"), rec.get("source"), rec.get("text"), rec.get("data")],
                                        sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
        if key in self.seen:
            self.skipped["duplicate"] += 1
            return None
        self.seen.add(key)
        return rec

    def content(self, value) -> dict:
        """A tool result's or message's text and media: text blocks joined, base64 media written once as files."""
        blocks = [{"type": "text", "text": value}] if isinstance(value, str) else value if isinstance(value, list) else []
        texts, media = [], []
        for b in blocks:
            if not isinstance(b, dict):
                continue
            src = b.get("source") if isinstance(b.get("source"), dict) else {}
            url = b.get("image_url") if isinstance(b.get("image_url"), str) else ""
            if b.get("type") in ("image", "document") and src.get("type") == "base64":
                media.append(self.media(src.get("data", ""), src.get("media_type", "")))
            elif url.startswith("data:") and ";base64," in url:  # Codex carries screenshots as data URLs
                mime, data = url[5:].split(";base64,", 1)
                media.append(self.media(data, mime))
            elif "text" in b:
                texts.append(str(b.get("text") or ""))
        out = {"text": "\n".join(texts)}
        return {**out, "media": media} if media else out

    def media(self, data: str, mime: str) -> dict:
        try:
            raw = base64.b64decode(data, validate=False)
        except (ValueError, TypeError):
            return {"type": mime, "error": "undecodable"}
        digest = hashlib.sha256(raw).hexdigest()
        name = f"media/{digest}.{MIME.get(mime, 'bin')}"
        target = self.folder / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f".{target.name}.{os.getpid()}")
            tmp.write_bytes(raw)
            os.replace(tmp, target)
        return {"file": name, "type": mime, "bytes": len(raw)}

    def blob(self, body: str) -> str:
        """The whole text, once per workspace, named by its hash; the record keeps the name."""
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        target = self.folder.parent.parent / "blobs" / digest[:2] / f"{digest}.txt"
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f".{target.name}.{os.getpid()}")
            tmp.write_text(body, encoding="utf-8")
            os.replace(tmp, target)
        return digest

    def emit(self, rec: dict | None) -> None:
        if rec is None:
            return
        if rec.get("kind") == "user":
            self.last_user = rec.get("text", "")
        if rec.get("kind") in ("system", "user"):  # the session-start hook names the project the session works on
            for found in ACTIVE_PROJECT.findall(str(rec.get("text") or "")):
                if found not in self.meta.setdefault("projects", []):
                    self.meta["projects"].append(found)
        if rec.get("at"):
            self.meta.setdefault("started", rec["at"])
            self.meta["last"] = rec["at"]
        rec = _clean({k: v for k, v in rec.items() if v not in (None, "", [], {})})
        if rec.get("kind") in BLOB_KINDS:
            for field in ("text", "input"):
                value = rec.get(field)
                body = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False) if value is not None else ""
                if len(body) > BLOB_CHARS:
                    rec[field], rec[f"{field}_blob"], rec[f"{field}_chars"] = body[:HEAD_CHARS], self.blob(body), len(body)
        line = json.dumps({"seq": self.seq, **rec}, ensure_ascii=False, default=str)
        self.lines.append(line + "\n")
        self.seq += 1

    def flush(self, offset: int) -> int:
        """Append the kept records, rotating segments, then record how far the native file was read."""
        written = 0
        while self.lines:
            target = self.folder / f"transcript-{self.segment:04d}.jsonl"
            size, batch = target.stat().st_size if target.exists() else 0, []
            while self.lines and (not size or size + len(self.lines[0]) <= SEGMENT_BYTES):
                size += len(self.lines[0])
                batch.append(self.lines.pop(0))
            if batch:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("a", encoding="utf-8") as out:
                    out.writelines(batch)
                written += len(batch)
            if self.lines:
                self.segment += 1
        self.offset = offset
        self.meta.update({"harness": self.harness, "session": self.session, "native": str(self.native),
                          "records": self.seq, "skipped": dict(self.skipped), "updated": _iso(time.time()),
                          "segments": self.segment})
        if self.folder:
            paths.write_json(self.folder / "meta.json", self.meta)
        paths.write_json(self.file, {"offset": self.offset, "seq": self.seq, "segment": self.segment,
                                     "folder": str(self.folder or ""), "seen": sorted(self.seen), "meta": self.meta,
                                     "model": self.model, "last_user": self.last_user[:2000]})
        return written


# --- the harnesses --------------------------------------------------------------------------------------------


def _claude(row: dict, s: _Session):
    t, at = row.get("type"), row.get("timestamp")
    if t in ("user", "assistant"):
        msg = row.get("message") if isinstance(row.get("message"), dict) else {}
        content = msg.get("content")
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content if isinstance(content, list) else []
        if t == "assistant":
            s.model = msg.get("model") or s.model
            for b in blocks:
                kind = b.get("type")
                if kind == "text":
                    yield {"at": at, "kind": "assistant", "text": b.get("text"), "model": s.model}
                elif kind == "thinking":
                    yield {"at": at, "kind": "reasoning", "text": b.get("thinking")}
                elif kind == "redacted_thinking":
                    yield {"at": at, "kind": "reasoning", "redacted": True}
                elif kind == "tool_use":
                    yield {"at": at, "kind": "tool_call", "id": b.get("id"), "tool": b.get("name"), "input": b.get("input")}
            return
        for b in blocks:
            kind = b.get("type")
            if kind == "tool_result":
                yield {"at": at, "kind": "tool_result", "id": b.get("tool_use_id"), "error": bool(b.get("is_error")),
                       **s.content(b.get("content"))}
            elif kind in ("text", "image", "document"):
                text = b.get("text") or ""
                who = ("compaction" if row.get("isCompactSummary") else
                       "system" if row.get("isMeta") or _injected(text) else "user")
                rec = {"at": at, "kind": who, **s.content([b])}
                yield s.once(rec) if who == "system" else rec
    elif t == "system":
        sub = row.get("subtype")
        if sub == "compact_boundary":
            yield {"at": at, "kind": "compaction", "data": row.get("compactMetadata")}
        else:
            yield s.once({"at": at, "kind": "system", "source": sub,
                          "text": row.get("content") or json.dumps(row.get("hookInfos") or row.get("error") or "")})
    elif t == "attachment":
        a = row.get("attachment") if isinstance(row.get("attachment"), dict) else {}
        body = a.get("content") or a.get("text") or a.get("prompt") or {k: v for k, v in a.items() if k != "type"}
        yield s.once({"at": at, "kind": "system", "source": a.get("type"),
                      "text": body if isinstance(body, str) else json.dumps(body, default=str)})
    elif t in CLAUDE_SKIP:
        s.skipped[t] += 1
    else:  # titles, agent names, PR and artifact links, modes, cost totals, queued prompts
        yield s.once({"at": at, "kind": "meta", "source": t,
                      "data": {k: v for k, v in row.items() if k not in ("type", "sessionId", "timestamp")}})


def _codex(row: dict, s: _Session):
    t, at, p = row.get("type"), row.get("timestamp"), row.get("payload") if isinstance(row.get("payload"), dict) else {}
    kind = p.get("type")
    if t == "session_meta":
        yield {"at": at, "kind": "session", "data": {k: p[k] for k in ("id", "cwd", "originator", "cli_version", "source",
                                                                       "model_provider", "git") if k in p}}
        if p.get("instructions"):
            yield s.once({"at": at, "kind": "system", "source": "instructions", "text": p["instructions"]})
    elif t == "turn_context":
        s.model = p.get("model") or s.model
        yield s.once({"at": at, "kind": "meta", "source": "turn_context", "data": {
            k: p[k] for k in ("model", "effort", "approval_policy", "sandbox_policy", "cwd", "summary") if k in p}})
    elif t == "response_item" and kind == "message":
        body = s.content(p.get("content"))
        text = body["text"]
        if p.get("role") == "assistant":
            yield {"at": at, "kind": "assistant", **body, "model": s.model}
        elif p.get("role") == "user" and not _injected(text):
            yield None if text == s.last_user else {"at": at, "kind": "user", **body}
        else:
            yield s.once({"at": at, "kind": "system", "source": p.get("role"), **body})
    elif t == "response_item" and kind == "reasoning":
        summary = "\n".join(str(x.get("text") or "") for x in p.get("summary") or [] if isinstance(x, dict))
        s.skipped["encrypted reasoning"] += bool(p.get("encrypted_content"))
        yield {"at": at, "kind": "reasoning", "text": summary} if summary else None
    elif t == "response_item" and kind and kind.endswith("_output"):
        out = p.get("output")
        out = out.get("content") if isinstance(out, dict) and "content" in out else out
        yield {"at": at, "kind": "tool_result", "id": p.get("call_id"),
               **(s.content(out) if isinstance(out, (str, list)) else {"text": json.dumps(out, default=str)})}
    elif t == "response_item" and kind and kind.endswith("_call"):
        yield {"at": at, "kind": "tool_call", "id": p.get("call_id") or p.get("id"), "tool": p.get("name") or kind,
               "input": p.get("arguments") or p.get("input") or p.get("action")}
    elif t == "event_msg" and kind == "user_message":
        text = str(p.get("message") or "")
        yield None if not text or text == s.last_user else {"at": at, "kind": "user", "text": text}
    elif t == "compacted":
        s.skipped["compaction history items"] += len(p.get("replacement_history") or [])
        yield {"at": at, "kind": "compaction", "text": p.get("message")}
    else:  # UI events that repeat the items above, token counters, world-state snapshots
        s.skipped[f"{t}:{kind}" if kind else str(t)] += 1


def _muse(row: dict, s: _Session):
    for frame in [row] + [c for c in row.get("children") or [] if isinstance(c, dict)]:
        at, kind = _iso(frame.get("recorded_at")), frame.get("payload_type")
        pl = frame.get("payload") if isinstance(frame.get("payload"), dict) else {}
        ev = pl.get("event") if isinstance(pl.get("event"), dict) else {}
        what = ev.get("kind")
        if kind == "runtime.session.metadata":
            yield {"at": at, "kind": "session", "data": pl.get("record")}
        elif kind == "runtime.user_intent.accepted":  # every prompt (113 in one session); only 13 were also displayed
            text = "\n".join(str(c.get("text") or "") for m in pl.get("model_messages") or [] if isinstance(m, dict)
                             for c in m.get("content") or [] if isinstance(c, dict) and c.get("kind") == "text")
            yield {"at": at, "kind": "user", "text": text} if text else None
        elif kind == "runtime.session" and what == "assistant_message_committed":
            yield {"at": at, "kind": "assistant", "text": ev.get("text"), "model": s.model}
        elif kind == "runtime.session" and what == "reasoning_committed":
            s.skipped["encrypted reasoning"] += bool(ev.get("encrypted_content"))
            yield {"at": at, "kind": "reasoning", "text": ev.get("text")} if ev.get("text") else None
        elif kind == "runtime.session" and what == "assistant_tool_calls_committed":
            for call in ev.get("tool_calls") or []:
                yield {"at": at, "kind": "tool_call", "id": call.get("call_id"), "tool": call.get("name"), "input": call.get("args")}
        elif kind == "runtime.session" and what == "tool_result_batch_committed":
            for result in ev.get("results") or []:
                yield {"at": at, "kind": "tool_result", "id": result.get("tool_call_id"), "text": result.get("text")}
        elif kind == "runtime.session" and what == "model_completed":
            s.model = ev.get("model") or s.model
        elif kind == "runtime.session" and what == "context_compaction_installed":
            yield {"at": at, "kind": "compaction", "text": (ev.get("replacement") or {}).get("text")}
        else:
            s.skipped[f"{kind}:{what}" if what else str(kind)] += 1


ADAPTERS = {"claude-code": _claude, "codex": _codex, "muse": _muse}


def _identity(harness: str, native: Path) -> str:
    if harness == "codex":
        return native.stem[-36:]
    if harness == "muse":
        return native.parent.name
    parts = native.parts  # a subagent's record sits under its parent session's subagents/ folder
    return f"{parts[parts.index('subagents') - 1]}-{native.stem}" if "subagents" in parts else native.stem


def _place(harness: str, native: Path, session: str) -> Path:
    """The session's folder, from where and when it began: the first rows that name a folder and a time."""
    cwd, when = "", ""
    with native.open("rb") as f:
        for raw in f.readlines(2_000_000)[:400]:
            try:
                row = json.loads(raw)
            except ValueError:
                continue
            frames = [row] + [c for c in row.get("children") or [] if isinstance(c, dict)] if isinstance(row, dict) else []
            for fr in frames:
                pl = fr.get("payload") if isinstance(fr.get("payload"), dict) else {}
                rec = pl.get("record") if isinstance(pl.get("record"), dict) else {}
                cwd = cwd or fr.get("cwd") or pl.get("cwd") or rec.get("cwd") or rec.get("workspace_root") or ""
                when = when or _iso(fr.get("timestamp") or fr.get("recorded_at") or pl.get("timestamp"))
            if cwd and when:
                break
    month = (when or _iso(native.stat().st_mtime))[:7]
    return root() / workspace_of(cwd) / month / f"{harness}-{session}"


def export_file(harness: str, native: Path, project: str = "") -> int:
    """Copy what the native transcript gained since the last export; returns how many records were kept."""
    native = Path(native)
    s = _Session(harness, native, _identity(harness, native))
    size = native.stat().st_size
    if size < s.offset:  # the harness rewrote the file: read it again from the start, under the same session
        s.offset = 0
        s.skipped["rewritten"] += 1
    if size == s.offset and not project:
        return 0
    s.folder = s.folder or _place(harness, native, s.session)
    if project and project not in s.meta.setdefault("projects", []):
        s.meta["projects"].append(project)
    adapter, end = ADAPTERS[harness], s.offset
    with native.open("rb") as f:
        f.seek(s.offset)
        for raw in f:
            if not raw.endswith(b"\n"):
                break  # a line still being written: the next export reads it whole
            end += len(raw)
            try:
                row = json.loads(raw)
            except ValueError:
                s.skipped["unreadable line"] += 1
                continue
            for rec in adapter(row, s) if isinstance(row, dict) else ():
                s.emit(rec)
    s.meta["models"] = sorted(set(s.meta.get("models", [])) | ({s.model} if s.model else set()))
    return s.flush(end)


def natives(days: float = 0) -> list:
    """(harness, path) for every native transcript, or those changed in the last `days` days."""
    since, found = time.time() - days * 86400 if days else 0, []
    for harness, base in paths.transcript_roots().items():
        pattern = {"claude-code": "*/**/*.jsonl", "codex": "**/rollout-*.jsonl", "muse": "*/*/*/*/session.jsonl"}[harness]
        found += [(harness, p) for p in base.glob(pattern) if p.is_file() and p.stat().st_mtime >= since]
    return found


def export(days: float = 0, only: str = "") -> list:
    """Export every native transcript changed in the last `days` days (all when 0); `only` names one session."""
    from synthesis import board
    report = []
    for harness, native in natives(days):
        session = _identity(harness, native)
        if only and only not in (session, native.stem, str(native)):
            continue
        live = board.load(native.stem) if harness == "claude-code" else board.load(session)
        try:
            kept = export_file(harness, native, getattr(live, "project", "") or "")
        except OSError as exc:
            report.append(f"{harness} {session}: not exported ({exc})")
            continue
        if kept:
            report.append(f"{harness} {session}: {kept} record(s)")
    return report


# --- reading what was kept ------------------------------------------------------------------------------------


def catalog(workspace: str = "", project: str = "") -> list:
    """Every exported session's meta, newest first."""
    pattern = f"{workspace or '*'}/*/*/meta.json"
    found = [dict(paths.read_json(m), folder=str(m.parent)) for m in root().glob(pattern)]
    found = [m for m in found if not project or project in m.get("projects", [])]
    return sorted(found, key=lambda m: m.get("last", ""), reverse=True)


def records(folder: str, kinds: tuple = (), whole: bool = False) -> list:
    """A session's records in order; `whole` puts each blob's full text back in place of its first characters."""
    rows = []
    for segment in sorted(Path(folder).glob("transcript-*.jsonl")):
        for line in segment.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not kinds or rec.get("kind") in kinds:
                rows.append(_whole(rec, Path(folder)) if whole else rec)
    return rows


def _whole(rec: dict, folder: Path) -> dict:
    for field in ("text", "input"):
        digest = rec.get(f"{field}_blob")
        blob = folder.parent.parent / "blobs" / str(digest)[:2] / f"{digest}.txt"
        if digest and blob.is_file():
            rec[field] = blob.read_text(encoding="utf-8")
    return rec


def recent(project: str = "", workspace: str = "", turns: int = 12) -> list:
    """The last `turns` prompts and replies in a project (any harness, any session), oldest first, each with its
    session: what a session picking the work up in another harness needs before the full record."""
    found = []
    for meta in catalog(workspace, project):
        for rec in reversed(records(meta["folder"], ("user", "assistant"))):
            found.append({**rec, "harness": meta.get("harness"), "session": meta.get("session")})
            if len(found) >= turns:
                break
        if len(found) >= turns:
            break
    return sorted(found, key=lambda r: r.get("at", ""))


def search(pattern: str, workspace: str = "", project: str = "", kinds: tuple = ()) -> list:
    rx = re.compile(pattern, re.I)
    return [{**rec, "session": meta.get("session"), "harness": meta.get("harness")}
            for meta in catalog(workspace, project) for rec in records(meta["folder"], kinds)
            if rx.search(json.dumps({k: rec.get(k) for k in ("text", "input", "tool")}, ensure_ascii=False))]


def render(rec: dict, width: int = 0) -> str:
    """One record as a readable line or block."""
    body = rec.get("text") or ""
    if rec.get("kind") == "tool_call":
        body = f"{rec.get('tool')} {json.dumps(rec.get('input'), ensure_ascii=False) if not isinstance(rec.get('input'), str) else rec.get('input')}"
    elif not body and rec.get("data"):
        body = json.dumps(rec.get("data"), ensure_ascii=False, default=str)
    body = body if not width or len(body) <= width else body[:width] + f" ... [{len(body) - width} more characters]"
    who = rec.get("kind", "?") + (f" ({rec['model']})" if rec.get("model") else "")
    return f"#{rec.get('seq', '?')} {rec.get('at', '')[:19]} {who}: {body}"
