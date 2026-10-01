from pathlib import Path
import json
import hashlib
from datetime import datetime, timezone, timedelta
import httpx
import pytest
import yaml

import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[2]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def test_meeting_entry_has_complete_window_owner():
    m = module(
        "skills/synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py",
        "acquisition_fetch_red",
    )
    assert callable(getattr(m, "acquire_window", None))


def test_slack_has_actual_acquisition_entry():
    assert (ROOT / "skills/synthesis-slack-sync/scripts/acquire.py").is_file()


def test_verified_runtime_registers_actual_acquisition_entries():
    m = module(
        "skills/synthesis-onboarding/scripts/release_runtime.py",
        "acquisition_runtime_red",
    )
    assert (
        "synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py"
        in m.PUBLIC_ENTRYPOINTS
    )
    assert "synthesis-slack-sync/scripts/acquire.py" in m.PUBLIC_ENTRYPOINTS


@pytest.fixture
def owners():
    fetch = module(
        "skills/synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py",
        "entry_fetch",
    )
    slack = module("skills/synthesis-slack-sync/scripts/acquire.py", "entry_slack")
    return fetch, slack


@pytest.fixture
def wire(monkeypatch):
    original = httpx.Client
    calls = []
    holder = {"handler": None}

    def endpoint(request):
        calls.append((request.method, request.url.path, dict(request.url.params)))
        status, value = holder["handler"](request)
        raw = value if isinstance(value, bytes) else json.dumps(value).encode()
        return httpx.Response(status, stream=httpx.ByteStream(raw), request=request)

    def client(*args, **kwargs):
        return original(*args, transport=httpx.MockTransport(endpoint), **kwargs)

    monkeypatch.setattr(httpx, "Client", client)
    monkeypatch.setenv("SYNTHETIC_ACQUISITION_TOKEN", "synthetic-not-a-credential")
    return holder, calls


def dates():
    end = datetime.now(timezone.utc) - timedelta(minutes=5)
    start = end - timedelta(hours=1)
    return start, end


def meeting_cfg(tmp_path):
    return {
        "workspace": "fixture",
        "google_account": "reader@example.invalid",
        "transcripts_repo": str(tmp_path / "repository"),
        "transcripts_path": "transcripts",
        "transcript_tab_id": "verbatim",
        "acquisition_adapter": {
            "kind": "google-rest-v1",
            "token": "env:SYNTHETIC_ACQUISITION_TOKEN",
            "folder_id": "folder123",
            "positive_control_id": "control123",
            "window_field": "createdTime",
        },
    }


def doc_body(docid, *, empty=False):
    def tab(key, text):
        return {
            "tabProperties": {"tabId": key},
            "documentTab": {
                "body": {
                    "content": [
                        {"paragraph": {"elements": [{"textRun": {"content": text}}]}}
                    ]
                }
            },
        }

    transcript = "".join(
        f"00:{i:02}:00\nAlice Chen: I will review item {i}.\nBob Smith: Agreed.\n"
        for i in range(10)
    )
    return {
        "documentId": docid,
        "tabs": [
            tab("verbatim", "" if empty else transcript),
            tab("notes", "Lossy notes only."),
        ],
    }


def google_handler(cfg, start, end, *, fault=None):
    def handle(request):
        path, args = request.url.path, dict(request.url.params)
        if path.endswith("/about"):
            return 200, {
                "user": {
                    "emailAddress": cfg["google_account"]
                    if fault != "account"
                    else "foreign@example.invalid"
                }
            }
        if path.endswith("/files/control123"):
            return 200, {
                "id": "control123",
                "mimeType": "application/vnd.google-apps.document",
                "parents": ["folder123"],
                "trashed": False,
            }
        if path.endswith("/files"):
            if fault == "http":
                return 401, {"error": "invalid_token"}
            if fault == "repeated":
                token = "again"
            else:
                token = "second" if "pageToken" not in args else None
            ident = "first" if "pageToken" not in args else "unrelated_title"
            value = {
                "kind": "drive#fileList",
                "incompleteSearch": False,
                "files": [
                    {
                        "id": ident,
                        "name": "No title relevance used",
                        "parents": ["folder123"],
                        "mimeType": "application/vnd.google-apps.document",
                        "createdTime": start.isoformat(),
                    }
                ],
            }
            if token:
                value["nextPageToken"] = token
            return 200, value
        if "/documents/" in path:
            result = doc_body(path.rsplit("/", 1)[-1], empty=fault == "empty")
            if fault == "wrong-document":
                result["documentId"] = "foreign"
            return 200, result
        raise AssertionError(path)

    return handle


def run_meeting(fetch, cfg, tmp_path, start, end, **kwargs):
    return fetch.acquire_window(
        cfg,
        mode="fetch",
        through=end.isoformat(),
        backfill=start.isoformat(),
        capture_root=tmp_path / "capture",
        evidence_path=tmp_path / "evidence.json",
        advance=True,
        home=tmp_path / "state",
        **kwargs,
    )


def test_actual_meeting_entry_pages_saves_and_advances(owners, wire, tmp_path):
    fetch, _ = owners
    holder, calls = wire
    cfg = meeting_cfg(tmp_path)
    start, end = dates()
    holder["handler"] = google_handler(cfg, start, end)
    result = run_meeting(fetch, cfg, tmp_path, start, end)
    assert result["watermark"]["moved"] is True
    assert len(result["saved_files"]) == 2
    assert len([c for c in calls if c[1].endswith("/files")]) == 2
    assert all(
        c[2]["includeTabsContent"] == "true" for c in calls if "/documents/" in c[1]
    )
    for row in result["saved_files"]:
        body = (
            Path(cfg["transcripts_repo"]) / cfg["transcripts_path"] / row["path"]
        ).read_text()
        assert (
            "Lossy notes only." in body and "Alice Chen: I will review item 9." in body
        )
    assert "synthetic-not-a-credential" not in (tmp_path / "evidence.json").read_text()


@pytest.mark.parametrize(
    "fault", ["account", "http", "repeated", "empty", "wrong-document"]
)
def test_meeting_actual_refusal_has_no_watermark(owners, wire, tmp_path, fault):
    fetch, _ = owners
    holder, calls = wire
    cfg = meeting_cfg(tmp_path)
    start, end = dates()
    holder["handler"] = google_handler(cfg, start, end, fault=fault)
    with pytest.raises(ValueError):
        run_meeting(fetch, cfg, tmp_path, start, end)
    assert not (tmp_path / "state").exists()
    assert len(calls) < 10


def test_mcp_selection_never_falls_back_to_direct_token(owners, wire, tmp_path):
    fetch, _ = owners
    holder, calls = wire
    cfg = meeting_cfg(tmp_path)
    cfg["acquisition_adapter"]["kind"] = "workspace-mcp"
    start, end = dates()
    with pytest.raises(ValueError, match="explicitly selected"):
        run_meeting(fetch, cfg, tmp_path, start, end)
    assert calls == []


def slack_cfg(tmp_path):
    return {
        "workspace": "fixture",
        "transcripts_repo": str(tmp_path / "repository"),
        "transcripts_path": "transcripts",
        "channels": [{"id": "C123", "name": "channel"}],
        "acquisition_adapter": {
            "kind": "slack-web-api-v1",
            "team_id": "T123",
            "user_id": "U123",
        },
    }


def registry(tmp_path):
    p = tmp_path / "registry.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "mode": "isolated",
                "workspaces": [
                    {
                        "name": "fixture",
                        "domain": "fixture.slack.com",
                        "token": "env:SYNTHETIC_ACQUISITION_TOKEN",
                    },
                    {
                        "name": "foreign",
                        "domain": "foreign.slack.com",
                        "token": "env:MUST_NOT_READ",
                    },
                ],
            }
        )
    )
    return p


def slack_handler(start, end, *, fault=None):
    parent = f"{int(start.timestamp()) - 100}.000000"
    reply = f"{int(start.timestamp()) + 10}.000000"
    body = {
        "ts": reply,
        "thread_ts": parent,
        "text": "first line\nUTF-8 café ```\nlast line",
        "user": "U123",
        "reactions": [{"name": "ok", "count": 1}],
        "files": [{"id": "F123"}],
    }
    old = {"ts": parent, "text": "old parent", "user": "U456", "reply_count": 1}

    def handle(request):
        name = request.url.path.rsplit("/", 1)[-1]
        args = dict(request.url.params)
        if name == "auth.test":
            return 200, {
                "ok": True,
                "team_id": "T123" if fault != "account" else "T999",
                "user_id": "U123",
                "url": "https://fixture.slack.com/",
            }
        if name == "conversations.info":
            return 200, {
                "ok": True,
                "channel": {"id": args["channel"], "name": "channel"},
            }
        if name == "conversations.history":
            if fault == "http":
                return 429, {"ok": False, "error": "ratelimited"}
            return 200, {
                "ok": True,
                "messages": [dict(body, thread_ts=parent)],
                "has_more": False,
                "response_metadata": {"next_cursor": ""},
            }
        if name == "search.messages":
            page = int(args["page"])
            hits = (
                []
                if fault == "empty"
                else [
                    {
                        **body,
                        "channel": {"id": "C123" if fault != "foreign" else "C999"},
                    }
                ]
            )
            return 200, {
                "ok": True,
                "messages": {
                    "matches": (
                        [{**old, "channel": {"id": "C123"}}] if page == 1 else hits
                    )
                    if fault != "empty"
                    else [],
                    "paging": {"page": page, "pages": 2, "count": 1, "total": 2},
                },
            }
        if name == "conversations.replies":
            assert "oldest" not in args
            rows = [old, body]
            if fault == "conflict":
                rows = [old, {**body, "text": "edited inconsistent source"}]
            return 200, {
                "ok": True,
                "messages": rows,
                "has_more": False,
                "response_metadata": {"next_cursor": ""},
            }
        raise AssertionError(name)

    return handle, parent, reply, body


def run_slack(slack, cfg, tmp_path, start, end, **kwargs):
    return slack.acquire(
        cfg,
        registry(tmp_path),
        through=end.isoformat(),
        backfill=start.isoformat(),
        capture_root=tmp_path / "capture",
        evidence_path=tmp_path / "evidence.json",
        advance=True,
        home=tmp_path / "state",
        **kwargs,
    )


def test_actual_slack_entry_old_parent_exact_text_and_watermark(owners, wire, tmp_path):
    _, slack = owners
    holder, calls = wire
    cfg = slack_cfg(tmp_path)
    start, end = dates()
    handler, parent, reply, body = slack_handler(start, end)
    holder["handler"] = handler
    result = run_slack(slack, cfg, tmp_path, start, end)
    assert result["watermark"]["moved"] is True
    saved = (
        Path(cfg["transcripts_repo"])
        / cfg["transcripts_path"]
        / result["saved_files"][0]["path"]
    )
    content = saved.read_text()
    assert body["text"] in content and f"**Message ID:** C123:{reply}" in content
    assert "old parent" in content
    assert [c[2]["page"] for c in calls if c[1].endswith("search.messages")] == [
        "1",
        "2",
    ]
    assert all(
        "oldest" not in c[2] for c in calls if c[1].endswith("conversations.replies")
    )
    assert (
        slack.thread_checker.extract_threads(None, content=content)[0]["ts"] == parent
    )


@pytest.mark.parametrize("fault", ["account", "http", "empty", "foreign", "conflict"])
def test_slack_actual_refusal_no_watermark(owners, wire, tmp_path, fault):
    _, slack = owners
    holder, calls = wire
    cfg = slack_cfg(tmp_path)
    start, end = dates()
    holder["handler"] = slack_handler(start, end, fault=fault)[0]
    with pytest.raises(ValueError):
        run_slack(slack, cfg, tmp_path, start, end)
    assert not (tmp_path / "state").exists()
    assert len(calls) < 10


def test_unresolved_dm_is_refused_before_transport(owners, wire, tmp_path):
    _, slack = owners
    holder, calls = wire
    cfg = slack_cfg(tmp_path)
    cfg["dm_channels"] = [{"name": "peer", "dm_id": "U999"}]
    start, end = dates()
    with pytest.raises(ValueError, match="resolve"):
        run_slack(slack, cfg, tmp_path, start, end)
    assert calls == []


def test_local_secret_never_in_error_or_raw_custody(owners, wire, tmp_path, capsys):
    fetch, _ = owners
    holder, calls = wire
    cfg = meeting_cfg(tmp_path)
    start, end = dates()
    holder["handler"] = google_handler(cfg, start, end, fault="http")
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump(cfg))
    rc = fetch.main(
        [
            "--mode",
            "fetch",
            "--config",
            str(config),
            "--through",
            end.isoformat(),
            "--backfill-from",
            start.isoformat(),
            "--capture-dir",
            str(tmp_path / "capture"),
            "--evidence",
            str(tmp_path / "evidence.json"),
            "--advance",
        ]
    )
    assert rc == 2
    assert "synthetic-not-a-credential" not in capsys.readouterr().out
    assert all(
        "synthetic-not-a-credential" not in p.read_text()
        for p in (tmp_path / "capture").glob("*.json")
    )


def test_actual_cli_google_fetch_and_health_planes(
    owners, wire, tmp_path, monkeypatch, capsys
):
    fetch, _ = owners
    holder, calls = wire
    cfg = meeting_cfg(tmp_path)
    start, end = dates()
    holder["handler"] = google_handler(cfg, start, end)
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump(cfg))
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "state"))
    args = [
        "--config",
        str(config),
        "--through",
        end.isoformat(),
        "--backfill-from",
        start.isoformat(),
        "--capture-dir",
        str(tmp_path / "capture"),
    ]
    assert fetch.main(["--mode", "health", *args]) == 0
    health = json.loads(capsys.readouterr().out)
    assert health["recorder"]["account"] == cfg["google_account"]
    assert len(calls) == 1 and not (tmp_path / "state").exists()
    assert (
        fetch.main(
            [
                "--mode",
                "fetch",
                *args,
                "--evidence",
                str(tmp_path / "evidence.json"),
                "--advance",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["watermark"]["moved"]


def test_actual_cli_slack_fetch_with_secret_free_status(
    owners, wire, tmp_path, monkeypatch, capsys
):
    _, slack = owners
    holder, calls = wire
    cfg = slack_cfg(tmp_path)
    start, end = dates()
    holder["handler"] = slack_handler(start, end)[0]
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump(cfg))
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "state"))
    args = [
        "--config",
        str(config),
        "--registry",
        str(registry(tmp_path)),
        "--through",
        end.isoformat(),
        "--backfill-from",
        start.isoformat(),
        "--capture-dir",
        str(tmp_path / "capture"),
        "--evidence",
        str(tmp_path / "evidence.json"),
        "--advance",
    ]
    assert slack.main(args) == 0
    text = capsys.readouterr().out
    result = json.loads(text)
    assert result["watermark"]["moved"]
    assert "first line" not in text and "synthetic-not-a-credential" not in text


@pytest.mark.parametrize("kind", ["google", "slack"])
def test_dependency_missing_refuses_before_credentials(
    owners, wire, tmp_path, monkeypatch, kind
):
    import builtins

    original = builtins.__import__

    def missing(name, *a, **kw):
        if name == "httpx":
            raise ImportError("synthetic dependency missing")
        return original(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", missing)
    monkeypatch.setenv("SYNTHETIC_ACQUISITION_TOKEN", "")
    fetch, slack = owners
    start, end = dates()
    with pytest.raises(ValueError, match="httpx missing"):
        if kind == "google":
            run_meeting(fetch, meeting_cfg(tmp_path), tmp_path, start, end)
        else:
            run_slack(slack, slack_cfg(tmp_path), tmp_path, start, end)
    assert wire[1] == []


@pytest.mark.parametrize(
    "fault", ["redirect", "malformed", "oversize", "gzip", "timeout"]
)
def test_transport_error_retains_bounded_custody(owners, wire, tmp_path, fault):
    import acquisition_transport as transport

    holder, calls = wire
    if fault == "timeout":

        def timeout(request):
            raise httpx.ReadTimeout("synthetic timeout")

        holder["handler"] = timeout
    elif fault == "redirect":
        holder["handler"] = lambda request: (302, b"location ignored")
    elif fault == "malformed":
        holder["handler"] = lambda request: (200, b"{broken")
    elif fault == "oversize":
        holder["handler"] = lambda request: (200, b"x" * (transport.MAX_RESPONSE + 1))
    else:
        original = httpx.Client

        # Preserve the real bounded producer but return an actual encoded header.
        def client(*a, **kw):
            client = original(*a, **kw)

            def encoded(request):
                return httpx.Response(
                    200,
                    headers={"content-encoding": "gzip"},
                    stream=httpx.ByteStream(b"not-decoded"),
                    request=request,
                )

            client._transport = httpx.MockTransport(encoded)
            return client

        # wire already injects its own transport; direct producer client is patched below.
        holder["handler"] = lambda request: (200, {"ok": False})
    capture = transport.Capture(tmp_path / "capture")
    owner = transport.ReadTransport("env:SYNTHETIC_ACQUISITION_TOKEN", capture)
    if fault == "gzip":
        owner.client._transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-encoding": "gzip"},
                stream=httpx.ByteStream(b"not-decoded"),
                request=request,
            )
        )
    with pytest.raises(ValueError):
        owner.call("auth.test")
    owner.close()
    assert capture.calls and capture.bytes <= transport.MAX_RESPONSE
    assert all(
        "synthetic-not-a-credential" not in Path(x["path"]).read_text()
        for x in capture.calls
    )


def test_fixed_endpoint_allowlist_refuses_mutation_before_http(owners, wire, tmp_path):
    import acquisition_transport as transport

    capture = transport.Capture(tmp_path / "capture")
    owner = transport.ReadTransport("env:SYNTHETIC_ACQUISITION_TOKEN", capture)
    for route in [
        "chat.postMessage",
        "conversations.join",
        "https://foreign.invalid/",
        "docs/../other",
    ]:
        with pytest.raises(ValueError, match="allowlist"):
            owner.call(route)
    owner.close()
    assert wire[1] == []


def test_known_current_and_previous_thread_union(owners, wire, tmp_path):
    _, slack = owners
    holder, calls = wire
    cfg = slack_cfg(tmp_path)
    start, end = dates()
    handler, parent, reply, body = slack_handler(start, end)
    root = Path(cfg["transcripts_repo"]) / cfg["transcripts_path"]
    root.mkdir(parents=True)
    second = f"{int(start.timestamp()) - 200}.000000"
    for name, ts in [("current.md", parent), ("previous.md", second)]:
        (root / name).write_text(f"## #channel (C123)\n#### Parent (TS: {ts})\n")
    cfg["known_archives"] = ["current.md", "previous.md"]

    def extended(request):
        if (
            request.url.path.endswith("conversations.replies")
            and request.url.params["ts"] == second
        ):
            return 200, {
                "ok": True,
                "messages": [
                    {"ts": second, "text": "known prior parent", "user": "U123"}
                ],
                "has_more": False,
            }
        return handler(request)

    holder["handler"] = extended
    result = run_slack(slack, cfg, tmp_path, start, end)
    assert result["watermark"]["moved"]
    assert {x[2]["ts"] for x in calls if x[1].endswith("conversations.replies")} == {
        parent,
        second,
    }


def test_partial_publication_and_idempotent_retry(owners, wire, tmp_path, monkeypatch):
    _, slack = owners
    holder, calls = wire
    cfg = slack_cfg(tmp_path)
    cfg["channels"].append({"id": "C456", "name": "other"})
    start, end = dates()
    base = slack_handler(start, end)[0]
    fail = {"yes": True}

    def multi(request):
        name = request.url.path.rsplit("/", 1)[-1]
        args = dict(request.url.params)
        if name == "conversations.info":
            return 200, {
                "ok": True,
                "channel": {
                    "id": args["channel"],
                    "name": "other" if args["channel"] == "C456" else "channel",
                },
            }
        if (
            name == "conversations.history"
            and args["channel"] == "C456"
            and fail["yes"]
        ):
            return 503, {"error": "synthetic unavailable"}
        code, value = base(request)
        if name == "search.messages" and "in:other " in args["query"]:
            for row in value["messages"]["matches"]:
                row["channel"]["id"] = "C456"
        return code, value

    holder["handler"] = multi
    with pytest.raises(ValueError):
        run_slack(slack, cfg, tmp_path, start, end)
    root = Path(cfg["transcripts_repo"]) / cfg["transcripts_path"]
    saved = list(root.rglob("*.md"))
    assert len(saved) == 1
    before = saved[0].read_bytes()
    assert not (tmp_path / "state").exists()
    fail["yes"] = False
    result = run_slack(slack, cfg, tmp_path, start, end)
    assert result["watermark"]["moved"] and saved[0].read_bytes() == before


def test_saved_evidence_recovery_and_late_mutation_refusal(
    owners, wire, tmp_path, monkeypatch
):
    _, slack = owners
    holder, calls = wire
    cfg = slack_cfg(tmp_path)
    start, end = dates()
    holder["handler"] = slack_handler(start, end)[0]
    original = slack.sync_watermark.advance

    def stop(*a, **kw):
        raise RuntimeError("synthetic interruption after exact evidence publication")

    monkeypatch.setattr(slack.sync_watermark, "advance", stop)
    with pytest.raises(RuntimeError):
        run_slack(slack, cfg, tmp_path, start, end)
    evidence = json.loads((tmp_path / "evidence.json").read_text())
    assert not (tmp_path / "state").exists()
    monkeypatch.setattr(slack.sync_watermark, "advance", original)
    observed = original(
        "fixture",
        "slack",
        evidence["through"],
        targets=evidence["declared_targets"],
        acquisition=evidence,
        home=tmp_path / "state",
        now=datetime.now(timezone.utc),
    )
    assert observed["moved"]
    state = slack.sync_watermark.store_path("fixture", tmp_path / "state")
    before = state.read_bytes()
    archived = Path(evidence["archive_root"]) / evidence["archives"][0]["path"]
    archived.write_text(archived.read_text() + "changed")
    with pytest.raises(ValueError, match="bytes differ"):
        original(
            "fixture",
            "slack",
            evidence["through"],
            targets=evidence["declared_targets"],
            acquisition=evidence,
            home=tmp_path / "state",
            now=datetime.now(timezone.utc),
        )
    assert state.read_bytes() == before


def test_slack_archive_hostile_parent_and_hardlink_refuse(owners, wire, tmp_path):
    import os

    _, slack = owners
    holder, calls = wire
    start, end = dates()
    holder["handler"] = slack_handler(start, end)[0]
    cfg = slack_cfg(tmp_path)
    result = run_slack(slack, cfg, tmp_path, start, end)
    assert result["watermark"]["moved"] is True
    evidence = json.loads((tmp_path / "evidence.json").read_text())
    channel = evidence["channels"][0]
    target = tmp_path / "target.md"
    target.write_text("foreign")
    os.link(target, tmp_path / "second.md")
    with pytest.raises(ValueError):
        slack.save_channel(target, channel, force=True)
    assert target.read_text() == "foreign"
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(foreign, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        slack.save_channel(alias / "escaped.md", channel)
    assert list(foreign.iterdir()) == []


def test_dm_aggregator_preserves_two_conversations_and_raw_variants(
    owners, wire, tmp_path
):
    _, slack = owners
    holder, calls = wire
    cfg = slack_cfg(tmp_path)
    cfg["channels"] = []
    cfg["dm_channels"] = [
        {"dm_id": "D123", "name": "first"},
        {"dm_id": "D456", "name": "second"},
    ]
    start, end = dates()
    base, parent, reply, body = slack_handler(start, end)

    def dm(request):
        name = request.url.path.rsplit("/", 1)[-1]
        args = dict(request.url.params)
        if name == "conversations.info":
            return 200, {
                "ok": True,
                "channel": {
                    "id": args["channel"],
                    "is_im": True,
                    "user": "U111" if args["channel"] == "D123" else "U222",
                },
            }
        code, value = base(request)
        if name == "search.messages":
            cid = "D123" if "in:<@U111>" in args["query"] else "D456"
            for row in value["messages"]["matches"]:
                row["channel"]["id"] = cid
        return code, value

    holder["handler"] = dm
    result = run_slack(slack, cfg, tmp_path, start, end)
    assert len(result["saved_files"]) == 1 and result["saved_files"][0][
        "path"
    ].endswith("/_dms.md")
    path = (
        Path(cfg["transcripts_repo"])
        / cfg["transcripts_path"]
        / result["saved_files"][0]["path"]
    )
    payload = slack.parse_archive(path.read_bytes())
    assert set(payload["channels"]) == {"D123", "D456"}
    for rows in payload["channels"].values():
        assert (
            rows[reply][0]["text"] == body["text"]
            and rows[reply][0]["files"] == body["files"]
        )
    assert result["watermark"]["moved"]


def test_archive_merge_race_refuses_new_foreign_bytes(
    owners, wire, tmp_path, monkeypatch
):
    _, slack = owners
    holder, calls = wire
    cfg = slack_cfg(tmp_path)
    start, end = dates()
    holder["handler"] = slack_handler(start, end)[0]
    result = run_slack(slack, cfg, tmp_path, start, end)
    assert result["watermark"]["moved"] is True
    evidence = json.loads((tmp_path / "evidence.json").read_text())
    path = Path(evidence["archive_root"]) / result["saved_files"][0]["path"]
    original = slack._publish

    def raced(target, body, **kw):
        target.write_text("concurrent foreign edit")
        return original(target, body, **kw)

    monkeypatch.setattr(slack, "_publish", raced)
    with pytest.raises(ValueError, match="changed after merge"):
        slack.save_channel(path, evidence["channels"][0], domain="fixture.slack.com")
    assert path.read_text() == "concurrent foreign edit"


def test_missing_message_marker_never_advances_even_with_new_file_hash(
    owners, wire, tmp_path
):
    _, slack = owners
    holder, calls = wire
    cfg = slack_cfg(tmp_path)
    start, end = dates()
    handler, parent, reply, body = slack_handler(start, end)
    holder["handler"] = handler
    run_slack(slack, cfg, tmp_path, start, end)
    evidence = json.loads((tmp_path / "evidence.json").read_text())
    path = Path(evidence["archive_root"]) / evidence["archives"][0]["path"]
    path.write_text(
        path.read_text().replace(
            f"**Message ID:** C123:{reply}", "missing source marker"
        )
    )
    evidence["archives"][0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    state = slack.sync_watermark.store_path("fixture", tmp_path / "state")
    before = state.read_bytes()
    with pytest.raises(ValueError, match="unresolved gaps"):
        slack.sync_watermark.advance(
            "fixture",
            "slack",
            evidence["through"],
            targets=["C123"],
            acquisition=evidence,
            home=tmp_path / "state",
            now=datetime.now(timezone.utc),
        )
    assert state.read_bytes() == before


def test_mechanical_input_measurement_is_explicitly_synthetic(
    owners, wire, tmp_path, monkeypatch, capsys
):
    import time

    fetch, _ = owners
    holder, calls = wire
    cfg = meeting_cfg(tmp_path)
    start, end = dates()
    holder["handler"] = google_handler(cfg, start, end)
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump(cfg))
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "state"))
    before = time.monotonic()
    assert (
        fetch.main(
            [
                "--mode",
                "fetch",
                "--config",
                str(config),
                "--through",
                end.isoformat(),
                "--backfill-from",
                start.isoformat(),
                "--capture-dir",
                str(tmp_path / "capture"),
                "--evidence",
                str(tmp_path / "evidence.json"),
                "--advance",
            ]
        )
        == 0
    )
    text = capsys.readouterr().out
    result = json.loads(text)
    receipt = {
        "kind": "synthetic-input-proxy-only",
        "wall_seconds": time.monotonic() - before,
        "raw_response_bytes": result["custody"]["response_bytes"],
        "status_utf8_bytes": len(text.encode()),
        "status_four_byte_token_proxy": (len(text.encode()) + 3) // 4,
        "actual_model_tokens": "UNKNOWN",
        "actual_provider_cost": "UNKNOWN",
        "live_savings": "NOT_MEASURED",
        "saved_files": result["saved_files"],
    }
    (tmp_path / "MEASUREMENT.json").write_text(json.dumps(receipt, indent=2))
    for saved in receipt["saved_files"]:
        data = (
            Path(cfg["transcripts_repo"]) / cfg["transcripts_path"] / saved["path"]
        ).read_bytes()
        assert hashlib.sha256(data).hexdigest() == saved["sha256"]
    assert "Alice Chen" not in text


def test_mcp_raw_capture_and_wrong_id_do_not_claim_absence(owners, tmp_path):
    fetch, _ = owners
    import acquisition_transport as transport
    from mcp_client import bounded_post, _parse_sse

    payload = b'{"jsonrpc":"2.0","id":999,"result":{"content":[]}}'
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(
                200, stream=httpx.ByteStream(payload), request=req
            )
        )
    ) as client:
        capture = transport.Capture(tmp_path / "capture")
        response = bounded_post(
            client,
            "http://localhost:8765/mcp",
            capture=capture,
            json={"method": "tools/call", "id": 2},
        )
    assert capture.calls
    with pytest.raises(ValueError, match="matching request ID"):
        _parse_sse(response.text)
    assert capture.bytes == len(payload)


@pytest.mark.parametrize("fault", ["missing-evidence", "relative-evidence", "bad-mode"])
def test_meeting_preflight_before_any_provider_effect(owners, wire, tmp_path, fault):
    fetch, _ = owners
    holder, calls = wire
    cfg = meeting_cfg(tmp_path)
    start, end = dates()
    holder["handler"] = google_handler(cfg, start, end)
    evidence = (
        None
        if fault == "missing-evidence"
        else (
            "relative.json"
            if fault == "relative-evidence"
            else tmp_path / "evidence.json"
        )
    )
    with pytest.raises(ValueError):
        fetch.acquire_window(
            cfg,
            mode="bad" if fault == "bad-mode" else "fetch",
            through=end.isoformat(),
            backfill=start.isoformat(),
            capture_root=tmp_path / "capture",
            evidence_path=evidence,
        )
    assert calls == []


@pytest.mark.parametrize(
    "fault", ["unsafe-name", "duplicate-name", "relative-evidence", "bad-mode"]
)
def test_slack_preflight_before_any_provider_effect(owners, wire, tmp_path, fault):
    _, slack = owners
    holder, calls = wire
    cfg = slack_cfg(tmp_path)
    start, end = dates()
    holder["handler"] = slack_handler(start, end)[0]
    if fault == "unsafe-name":
        cfg["channels"][0]["name"] = "../foreign"
    if fault == "duplicate-name":
        cfg["channels"].append({"id": "C456", "name": "channel"})
    with pytest.raises(ValueError):
        slack.acquire(
            cfg,
            registry(tmp_path),
            mode="bad" if fault == "bad-mode" else "fetch",
            through=end.isoformat(),
            backfill=start.isoformat(),
            capture_root=tmp_path / "capture",
            evidence_path="relative.json"
            if fault == "relative-evidence"
            else tmp_path / "evidence.json",
        )
    assert calls == []


def test_mcp_bounded_failure_retains_partial_raw_custody(owners, monkeypatch, tmp_path):
    fetch, _ = owners
    import acquisition_transport

    m = sys.modules["mcp_client"]
    monkeypatch.setattr(m, "MAX_RESPONSE_BYTES", 65536)
    capture = acquisition_transport.Capture(tmp_path / "capture")
    response = httpx.Response(
        200,
        stream=httpx.ByteStream(b"x" * 131072),
        request=httpx.Request("POST", "https://fixture.invalid/mcp"),
    )

    class Client:
        @__import__("contextlib").contextmanager
        def stream(self, *a, **kw):
            yield response

    with pytest.raises(ValueError):
        m.bounded_post(
            Client(),
            "https://fixture.invalid/mcp",
            capture=capture,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "get_doc_content", "arguments": {}},
            },
        )
    assert len(capture.calls) == 1
    raw = json.loads(Path(capture.calls[0]["path"]).read_bytes())
    assert raw["error"] == "INCOMPLETE_RESPONSE"
    assert raw["raw_sha256"] == hashlib.sha256(b"x" * 65536).hexdigest()


def test_provider_credential_echo_never_enters_capture(owners, wire, tmp_path):
    import acquisition_transport

    holder, calls = wire
    holder["handler"] = lambda request: (401, {"error": "synthetic-not-a-credential"})
    capture = acquisition_transport.Capture(tmp_path / "capture")
    transport = acquisition_transport.ReadTransport(
        "env:SYNTHETIC_ACQUISITION_TOKEN", capture
    )
    try:
        with pytest.raises(ValueError):
            transport.call("auth.test")
    finally:
        transport.close()
    records = [Path(row["path"]).read_bytes() for row in capture.calls]
    import base64

    assert all(
        b"synthetic-not-a-credential"
        not in base64.b64decode(json.loads(raw)["raw_base64"])
        for raw in records
    )
    assert json.loads(records[0])["error"] == "CREDENTIAL_ECHO_BODY_WITHHELD"


def test_meeting_header_binds_exact_raw_response(owners, wire, tmp_path):
    fetch, _ = owners
    holder, _ = wire
    cfg = meeting_cfg(tmp_path)
    start, end = dates()
    holder["handler"] = google_handler(cfg, start, end)
    result = run_meeting(fetch, cfg, tmp_path, start, end)
    records = [
        json.loads(path.read_bytes()) for path in (tmp_path / "capture").glob("*.json")
    ]
    for receipt in result["saved_files"]:
        source_id = Path(receipt["path"]).stem
        capture = next(row for row in records if row["route"] == "docs/" + source_id)
        saved = (
            Path(cfg["transcripts_repo"]) / cfg["transcripts_path"] / receipt["path"]
        )
        assert "**Raw response SHA256:** " + capture["raw_sha256"] in saved.read_text()


@pytest.mark.parametrize("family", ["meeting", "slack"])
def test_missing_yaml_actual_entry_refuses_before_effect(
    owners, wire, monkeypatch, tmp_path, family
):
    import builtins

    original = builtins.__import__

    def unavailable(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("synthetic missing dependency", name="yaml")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", unavailable)
    if family == "meeting":
        with pytest.raises(SystemExit) as error:
            module(
                "skills/synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py",
                "missing_yaml_fetch",
            )
        assert error.value.code == 2
    else:
        _, slack = owners
        assert (
            slack.main(
                [
                    "--config",
                    str(tmp_path / "config"),
                    "--registry",
                    str(tmp_path / "registry"),
                    "--through",
                    "2026-09-27T00:00:00Z",
                    "--backfill-from",
                    "2026-09-26T00:00:00Z",
                    "--capture-dir",
                    str(tmp_path / "capture"),
                    "--evidence",
                    str(tmp_path / "evidence.json"),
                ]
            )
            == 2
        )
    assert wire[1] == []


def test_mcp_compressed_frame_refuses_before_expansion(owners, tmp_path):
    import gzip
    from acquisition_transport import Capture

    m = sys.modules["mcp_client"]
    capture = Capture(tmp_path / "capture")
    encoded = gzip.compress(b'{"private":"body"}')

    def response(request):
        return httpx.Response(
            200,
            stream=httpx.ByteStream(encoded),
            headers={"content-encoding": "gzip"},
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        with pytest.raises(ValueError):
            m.bounded_post(
                client,
                "https://fixture.invalid/mcp",
                capture=capture,
                json={"method": "tools/call", "id": 2},
            )
    assert (
        json.loads(Path(capture.calls[0]["path"]).read_bytes())["error"]
        == "INCOMPLETE_RESPONSE"
    )
