"""Agent session transcripts, kept in one plain form for every harness (R1.3, R1.4, R9.2).

Claude Code, Codex and Muse each keep a session's record in their own folder and format. Claude Code deletes its
copies after `cleanupPeriodDays` (30 by default), Codex is moving its rollouts into a database, and Muse keeps an event
log, so the only full record of what was asked, decided and done can disappear or change shape. `export` copies each
session, incrementally, into <home>/sessions/<workspace>/<YYYY-MM>/<harness>-<session>/ as one JSON record per event:
the principal's prompts, replies, reasoning, tool calls and results, compactions, the models that answered. Secrets are
masked with the commit check's credential patterns, images are kept once as files named by their hash, and text a
harness repeats every turn is kept once. A native file is read only past the offset already exported. Only the
principal's own words are `user` records: a prompt one agent writes to another is a `brief`, and an approval reviewer's
copy of the conversation is counted, not kept (R10.1). `sync` copies each workspace's conversation and tool calls into
that workspace's own sessions repo (R10.2, R10.3). Nothing here runs in a hook (R8.3): resume, handoff, checkpoints
and the rituals call it.
"""

from __future__ import annotations

import base64
import collections
import hashlib
import json
import os
import re
import subprocess
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
BLOB_KINDS = ("tool_result", "tool_call", "system", "brief")
# What leaves the Mac (R10.3, ruled 2026-10-30): the conversation and each tool call. Tool output, injected text, long
# text and images stay in the local archive.
SYNC_KINDS = ("session", "meta", "user", "brief", "assistant", "reasoning", "compaction", "tool_call")
GLOB = set("*?[")
INJECTED = ("<system-reminder>", "<command-", "<local-command-", "<task-notification>", "<ci-monitor-event>",
            "<environment_context>", "<user_instructions>", "# AGENTS.md instructions", "<permissions instructions>",
            # measured 2026-10-30 among records filed as prompts: automations, harness context and UI events
            "<heartbeat>", "<recommended_plugins>", "<external_codex_apps", "<in-app-browser-context", "<hook_prompt",
            "<user_action>", "<scheduled-task", "<skill>", "<create-pr-command>", "[Request interrupted by user")
AGENT_WRITTEN = ("<cross-session-message",)  # another session's message arrives as a prompt
MIME = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp", "application/pdf": "pdf"}
# Claude Code rows that only repeat or instrument what other rows hold: request copies, file backups, sync markers.
CLAUDE_SKIP = {"api-request", "api-request-blob", "api-request-shape", "file-history-snapshot", "file-history-delta",
               "bridge-session", "atis-latch", "last-prompt", "artifact-comment-monitor", "artifact-autoreact-ledger"}
ACTIVE_PROJECT = re.compile(r"Active project: ([A-Za-z0-9][A-Za-z0-9._-]*)")
# Where the session-start hook's own text arrives: Claude Code's hook attachments, or a message that starts with the
# hook's first line (Codex's developer message). Any other text that merely quotes the line names no project.
HOOK_SOURCES = ("hook_additional_context", "hook_success")


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


def _prompt(s: "_Session", at, body: dict, sidechain: bool = False):
    """A prompt as the record it really is: the principal's words, an agent's brief, or a reviewer's copy."""
    if s.meta.get("role") == "reviewer":  # Codex's approval reviewer is handed the whole conversation to judge
        s.skipped["reviewer's copy of the conversation"] += 1
        return None
    agent = sidechain or s.meta.get("role") == "subagent" or body.get("text", "").lstrip().startswith(AGENT_WRITTEN)
    return {"at": at, "kind": "brief" if agent else "user", **body}


def _workspaces() -> list:
    """Every workspace folder (config `workspace_roots`, default ~/workspaces/*)."""
    found = []
    for pattern in paths.config().get("workspace_roots") or ["~/workspaces/*"]:
        base = Path(os.path.expanduser(pattern))
        found += [f for f in (base.parent.glob(base.name) if GLOB & set(base.name) else [base]) if f.is_dir()]
    return found


def workspace_of(cwd: str) -> str:
    """The name of the workspace folder that holds cwd, or "other"."""
    here = os.path.realpath(os.path.expanduser(cwd or "~"))
    return next((f.name for f in _workspaces() if paths.inside(here, os.path.realpath(f))), "other")


def workspace_named(encoded: str) -> str:
    """The workspace of a Claude Code project folder, whose name is the start folder with every character other
    than a letter or digit turned into '-'; matched against each workspace, longest first, never decoded."""
    best = ("", "other")
    for f in _workspaces():
        enc = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(f))
        if (encoded == enc or encoded.startswith(enc + "-")) and len(enc) > len(best[0]):
            best = (enc, f.name)
    return best[1]


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
        if rec.get("kind") in ("user", "brief"):
            self.last_user = rec.get("text", "")
        text = str(rec.get("text") or "")
        if rec.get("kind") == "system" and (rec.get("source") in HOOK_SOURCES or text.lstrip().startswith("Local time:")):
            for found in ACTIVE_PROJECT.findall(text):  # the session-start hook names the project the session works on
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
                if row.get("isCompactSummary") or row.get("isMeta") or _injected(text):
                    who = "compaction" if row.get("isCompactSummary") else "system"
                    rec = {"at": at, "kind": who, **s.content([b])}
                    yield s.once(rec) if who == "system" else rec
                else:  # a sub-agent's prompts (isSidechain) are written by the agent that started it
                    yield _prompt(s, at, s.content([b]), bool(row.get("isSidechain")))
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
        sub = p.get("source", {}).get("subagent") if isinstance(p.get("source"), dict) else None
        if isinstance(sub, dict):  # a child thread: Codex's approval reviewer ("guardian") or a spawned agent
            s.meta["role"] = "reviewer" if sub.get("other") == "guardian" else "subagent"
            s.meta["parent"] = p.get("parent_thread_id") or (sub.get("thread_spawn") or {}).get("parent_thread_id")
        yield {"at": at, "kind": "session", "data": {k: p[k] for k in ("id", "cwd", "originator", "cli_version", "source",
                                                                       "parent_thread_id", "model_provider", "git") if k in p}}
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
            yield None if text == s.last_user else _prompt(s, at, body)
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
        yield None if not text or text == s.last_user or _injected(text) else _prompt(s, at, {"text": text})
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
            yield _prompt(s, at, {"text": text}) if text and not _injected(text) else None
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


def _place(harness: str, native: Path, session: str) -> tuple:
    """The session's folder and working folder, from where and when it began: the first rows that name a folder and
    a time. A sub-agent belongs to the workspace its parent ran in, wherever it then worked."""
    cwd, when, parent = "", "", ""
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
                parent = parent or pl.get("parent_thread_id") or ""
            if cwd and when:
                break
    month, workspace = (when or _iso(native.stat().st_mtime))[:7], workspace_of(cwd) if cwd else "other"
    if harness == "claude-code" and "projects" in native.parts:  # filed under the folder the session started in
        named = workspace_named(native.parts[native.parts.index("projects") + 1])
        workspace = named if named != "other" and ("subagents" in native.parts or workspace == "other") else workspace
    elif harness == "codex" and workspace == "other" and parent:
        folder = paths.read_json(root() / ".state" / f"codex-{parent}.json").get("folder")
        workspace = Path(folder).parts[-3] if folder else workspace
    return root() / workspace / month / f"{harness}-{session}", cwd


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
    if not s.folder:
        s.folder, s.meta["cwd"] = _place(harness, native, s.session)
        if harness == "claude-code" and "subagents" in native.parts:  # its prompts are the parent agent's briefs
            s.meta.update(role="subagent", parent=native.parts[native.parts.index("subagents") - 1])
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
        bases = [base, base.parent / "archived_sessions"] if harness == "codex" else [base]  # Codex moves archived ones
        found += [(harness, p) for b in bases for p in b.glob(pattern) if p.is_file() and p.stat().st_mtime >= since
                  and p.name != "journal.jsonl"]  # a Claude Code workflow's run journal, not a conversation
    return found


def rebuild() -> str:
    """Move the whole archive aside, never deleting it, so the next export reads every transcript again with the
    current adapters. Returns where the old archive went."""
    target = paths.home() / "archive" / f"sessions-{time.strftime('%Y%m%dT%H%M%S')}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if root().exists():
        os.replace(root(), target)
    return str(target)


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


def catalog(workspace: str = "", project: str = "", local_only: bool = False) -> list:
    """Every session's meta, newest first: this Mac's archive, then sessions other Macs synced into the workspace
    sessions repos that this Mac has cloned."""
    pattern = f"{workspace or '*'}/*/*/meta.json"
    found = [dict(paths.read_json(m), folder=str(m.parent)) for m in root().glob(pattern)]
    if not local_only:
        have = {(m.get("harness"), m.get("session")) for m in found}
        for ws, repo in repos().items():
            for m in repo.glob("*/*/meta.json") if not workspace or ws == workspace else ():
                meta = dict(paths.read_json(m), folder=str(m.parent), synced=ws)
                found += [meta] if (meta.get("harness"), meta.get("session")) not in have else []
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


def find(prefix: str) -> list:
    """The sessions a citation's id names: the exact id, else the one main session it starts (a sub-agent's id
    starts with its parent's, so `d20ab7c4` would otherwise match every agent that session started), else every
    session it starts."""
    found = [m for m in catalog() if prefix and str(m.get("session", "")).startswith(prefix)]
    exact = [m for m in found if m.get("session") == prefix]
    main = [m for m in found if m.get("role") not in ("subagent", "reviewer") and "-agent-" not in str(m.get("session"))]
    return exact or (main if len(main) == 1 else found)


def around(folder: str, seq: int, span: int = 3) -> list:
    """The record a citation names (`<harness> <session> #<seq>`, R10.5) with `span` records either side."""
    return [r for r in records(folder) if abs(int(r.get("seq", -1)) - seq) <= span]


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


# --- copying each workspace's conversation off the Mac (R10.2 to R10.4) ---------------------------------------


def repos() -> dict:
    """Workspace -> its sessions repo checkout (config `sessions_repos`). A session with no workspace is never
    synced (R10.4)."""
    found = paths.config().get("sessions_repos") or {}
    return {ws: Path(os.path.expanduser(p)) for ws, p in found.items() if ws != "other" and isinstance(p, str)}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=900)


def sync(workspace: str = "", push: bool = True) -> list:
    """Export what is new, then copy each workspace's conversation and tool calls into its sessions repo, one
    commit per month touched, and push. A line starting FAILED means that workspace's copy is not on its upstream."""
    targets = {ws: repo for ws, repo in repos().items() if not workspace or ws == workspace}
    if not targets:
        return []
    export(2)
    return [line for ws, repo in sorted(targets.items()) for line in _sync_workspace(ws, repo, push)]


def _sync_workspace(ws: str, repo: Path, push: bool) -> list:
    if not (repo / ".git").exists():
        return [f"FAILED {ws}: {repo} is not a git checkout; clone the workspace's sessions repo there"]
    state_file = root() / ".state" / f"sync-{ws}.json"
    state = paths.read_json(state_file)
    done, months, lines = dict(state.get("sessions", {})), collections.Counter(), []
    for meta in catalog(ws, local_only=True):
        rel = Path(meta["folder"]).relative_to(root() / ws).as_posix()
        if done.get(rel) != meta.get("records"):
            months[rel.split("/")[0]] += _write_synced(Path(meta["folder"]), repo / rel, meta)
            done[rel] = meta.get("records")
    for month, count in sorted(months.items()):
        added = _git(repo, "add", "-A", "--", month)
        if added.returncode:
            return lines + [f"FAILED {ws}: git add {month}: {added.stderr.strip()[-300:]}"]
        if _git(repo, "diff", "--cached", "--quiet").returncode == 0:
            continue
        made = _git(repo, "commit", "-q", "-m", f"Sessions: {month} ({count} changed)")
        if made.returncode:  # the commit check refused, or git failed: nothing is recorded as synced
            return lines + [f"FAILED {ws}: commit for {month} refused: {(made.stdout + made.stderr).strip()[-600:]}"]
        lines.append(f"{ws}: {month}: {count} session(s) committed")
    if push:
        if _git(repo, "rev-parse", "--abbrev-ref", "@{u}").returncode:
            pushed = _git(repo, "push", "-q", "-u", "origin", "HEAD")
        else:
            pulled = _git(repo, "pull", "-q", "--rebase")
            if pulled.returncode:
                return lines + [f"FAILED {ws}: pull --rebase: {pulled.stderr.strip()[-300:]}"]
            pushed = _git(repo, "push", "-q")
        if pushed.returncode:
            return lines + [f"FAILED {ws}: push: {pushed.stderr.strip()[-300:]}"]
    paths.write_json(state_file, {"sessions": done, "synced": _iso(time.time()), "pushed": push})
    return lines + [f"{ws}: {repo.name} up to date" + ("" if push else " (not pushed)")]


def _write_synced(src: Path, dst: Path, meta: dict) -> int:
    """Write a session's synced copy from the archive, whole and in order, so the same records always give the same
    files: closed segments never change and a rebuilt archive simply rewrites them. Returns 1 if anything changed."""
    segments, size = [[]], 0
    for rec in records(str(src), SYNC_KINDS):
        line = json.dumps(_clean(rec), ensure_ascii=False) + "\n"
        if segments[-1] and size + len(line.encode("utf-8")) > SEGMENT_BYTES:
            segments.append([])
            size = 0
        segments[-1].append(line)
        size += len(line.encode("utf-8"))
    dst.mkdir(parents=True, exist_ok=True)
    changed, wanted = 0, set()
    for number, lines in enumerate(segments, 1):
        target = dst / f"transcript-{number:04d}.jsonl"
        wanted.add(target.name)
        body = "".join(lines)
        if not target.exists() or target.read_text(encoding="utf-8") != body:
            target.write_text(body, encoding="utf-8")
            changed = 1
    for old in dst.glob("transcript-*.jsonl"):
        if old.name not in wanted:  # fewer records after a rebuild; git history keeps the old file
            old.unlink()
            changed = 1
    kept = {k: v for k, v in meta.items() if k not in ("folder", "native", "updated")}
    if changed or not (dst / "meta.json").exists():
        paths.write_json(dst / "meta.json", {**kept, "synced_kinds": list(SYNC_KINDS)})
    return changed
