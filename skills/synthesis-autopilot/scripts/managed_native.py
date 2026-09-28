"""Managed Codex transport through the existing finite native connection owner.

Explicit native permission selection replaces neither PM admission nor observed
OS protection. No global config mutation, hook trust, unsandboxed shell command,
user task, or provider turn is implied by callback/probe capability.
"""

from __future__ import annotations
import json
import hashlib
from pathlib import Path
import re
import native_resume
import managed_permissions as policy
from copy import deepcopy

MAX_BYTES = 1024 * 1024
STUDY_PROTOCOL = "codex-managed-probe-turn-v1"
METHODS = frozenset(
    {
        "initialize",
        "initialized",
        "config/read",
        "account/read",
        "thread/start",
        "thread/read",
        "thread/resume",
        "turn/start",
        "command/exec",
    }
)


def restrict_connection(connection, configuration, *, before_effect=None):
    """Deny all outbound bytes except the exact owner-built request sequence.

    This guards send itself, including calls originating inside the shared
    transport. No process/*, thread/shellCommand, approval reply, alias or unknown
    method can be emitted. Experimental schema support is not execution authority.
    """
    expected = deepcopy(requests(configuration))
    original = connection.send
    position = 0

    def send(value):
        nonlocal position
        if (
            not isinstance(value, dict)
            or value.get("method") not in METHODS
            or position >= len(expected)
            or value != expected[position]
        ):
            raise ValueError("Unadmitted managed outbound request refused before write")
        if value["method"] == "turn/start":
            # A turn-specific notification before our admitted request cannot
            # establish this turn's completion or protection. Preserve genuine
            # SessionStart/thread notifications and refuse foreign/preplayed
            # foreground work before emitting another productive effect.
            native_resume._finish_received_frame(connection)
            from native_callback import _rows as strict_rows

            for row in strict_rows(bytes(connection.raw_stdout)):
                method = row.get("method")
                params = row.get("params", {})
                if isinstance(method, str) and (
                    method.startswith(("turn/", "item/"))
                    or (isinstance(params, dict) and params.get("turnId") is not None)
                ):
                    raise ValueError(
                        "Native productive notification preceded its request"
                    )
        if (
            value["method"]
            in {"thread/start", "thread/resume", "command/exec", "turn/start"}
            and before_effect is not None
        ):
            before_effect()
        original(value)
        position += 1

    connection.send = send

    def admit_effect(sid):
        if position != len(expected):
            raise ValueError(
                "Managed effect cannot precede the exact readback sequence"
            )
        actions = effect_requests(configuration, sid)
        expected.extend(deepcopy(actions))
        return actions

    return admit_effect


def _rpc(identity, method, params):
    return {"jsonrpc": "2.0", "id": identity, "method": method, "params": params}


def _base_requests(configuration, *, allow_resume_growth=False):
    contract, selected = configuration["file_contract"], configuration["selected"]
    profile = policy.validate(contract)
    if configuration.get("client") != "codex" or any(
        not isinstance(selected.get(k), str) or not selected[k]
        for k in ("model", "model_reasoning_effort")
    ):
        raise ValueError("Managed invocation requires exact native model and effort")
    allocating = allocation_binding(configuration) is not None
    if productive(configuration) and profile["probe"] is None:
        raise ValueError("Managed productive work requires its exact canonical probe")
    planned = [
        _rpc(
            1,
            "initialize",
            {
                "clientInfo": {"name": "synthesis_callback_observer", "version": "1"},
                # Named permissions require this schema opt-in in the current
                # official app-server contract. restrict_connection guards every
                # outgoing byte with exact owner-built requests; process/* and
                # unsandboxed thread/shellCommand remain impossible to emit.
                # No host configuration, trust or permission profile is widened.
                "capabilities": {"experimentalApi": True},
            },
        ),
        {"jsonrpc": "2.0", "method": "initialized", "params": {}},
        _rpc(
            2, "config/read", {"cwd": contract["scratch_root"], "includeLayers": False}
        ),
        _rpc(
            3,
            "thread/start",
            {
                "cwd": contract["scratch_root"],
                "model": selected["model"],
                "approvalPolicy": "never",
                "permissions": profile["id"],
                "ephemeral": not allocating,
                "config": {
                    "model_reasoning_effort": selected["model_reasoning_effort"]
                },
            },
        ),
        _rpc(
            4, "config/read", {"cwd": contract["scratch_root"], "includeLayers": False}
        ),
    ]

    if configuration.get("resume") is not None:
        resume = resume_binding(configuration, allow_growth=allow_resume_growth)
        options = planned[3]["params"].copy()
        options.pop("ephemeral")
        options.update(threadId=resume["session_id"], excludeTurns=True)
        planned = planned[:3] + [
            _rpc(
                3,
                "thread/read",
                {"threadId": resume["session_id"], "includeTurns": False},
            ),
            _rpc(4, "thread/resume", options),
            _rpc(5, "config/read", planned[2]["params"]),
            _rpc(
                6,
                "thread/read",
                {"threadId": resume["session_id"], "includeTurns": False},
            ),
        ]
    return planned


def account_scope(configuration):
    """Existing admitted scoped account record; no credential material is read."""
    from native_protection import read_pinned_bytes

    selected = configuration.get("resume") or configuration.get("allocation")
    if selected is None:
        if configuration.get("required_capabilities") == ["managed-study-turn"]:
            raise ValueError(
                "Managed study work requires its existing scoped account admission"
            )
        return None
    ref = selected.get("account_scope")
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise ValueError("Exact scoped account artifact is required")
    value = native_resume._decode_frame(read_pinned_bytes(ref, limit=128 * 1024))
    if (
        not isinstance(value, dict)
        or value.get("kind") != "scoped-evaluation-account"
        or type(value.get("schema_version")) is not int
        or value["schema_version"] != 1
        or not isinstance(value.get("account_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", value["account_sha256"])
    ):
        raise ValueError("Scoped account artifact has no exact account identity")
    return value


def account_request(label):
    return _rpc("synthesis-account-" + label, "account/read", {"refreshToken": False})


def verify_account(configuration, value):
    scope = account_scope(configuration)
    account = value.get("account") if isinstance(value, dict) else None
    routing = value.get("workspaceRouting") if isinstance(value, dict) else None
    if (
        scope is None
        or not isinstance(account, dict)
        or account.get("type") != "chatgpt"
        or value.get("requiresOpenaiAuth") is not True
        or not isinstance(routing, dict)
        or not isinstance(routing.get("chatgptAccountId"), str)
        or hashlib.sha256(routing["chatgptAccountId"].encode()).hexdigest()
        != scope["account_sha256"]
        or routing.get("backendOrigin") != "https://chatgpt.com"
        or routing.get("accountRoutingOverride") not in {"NO_CONSTRAINT", "us", "us_cr"}
    ):
        raise ValueError(
            "Native effective account/provider does not match scoped evaluation"
        )
    return True


def account_read(connection, configuration, label):
    from native_callback import _rows

    request = account_request(label)
    prior = bytes(connection.raw_stdout)
    if prior and (
        not prior.endswith(b"\n")
        or any(row.get("id") == request["id"] for row in _rows(prior))
    ):
        raise ValueError("Native account response predates its fresh request frontier")
    connection.send(request)
    while True:
        raw = bytes(connection.raw_stdout)
        if raw and raw.endswith(b"\n"):
            found = [x for x in _rows(raw) if x.get("id") == request["id"]]
            if len(found) > 1:
                raise ValueError("Duplicate native account readback")
            if found:
                if (
                    set(found[0]) - {"jsonrpc", "id", "result"}
                    or "result" not in found[0]
                ):
                    raise ValueError("Native account readback failed")
                verify_account(configuration, found[0]["result"])
                return
        connection._read()


def requests(configuration, *, allow_resume_growth=False):
    planned = _base_requests(configuration, allow_resume_growth=allow_resume_growth)
    if account_scope(configuration) is not None:
        index = next(
            i
            for i, x in enumerate(planned)
            if x["method"] in {"thread/start", "thread/resume"}
        )
        planned.insert(index, account_request("before-session"))
    return planned


def allocation_binding(configuration):
    """Model-free persistent allocation is separately admitted by the same owner."""
    from native_protection import read_pinned_bytes

    flag = configuration.get("persistent_allocation", False)
    if type(flag) is not bool:
        raise ValueError("Persistent allocation must be explicitly typed")
    value = configuration.get("allocation")
    if not flag:
        if value is not None:
            raise ValueError("Allocation binding without its explicit purpose")
        return None
    if configuration.get("resume") is not None or configuration.get(
        "required_capabilities"
    ) != ["native-callback"]:
        raise ValueError(
            "Persistent allocation is model-free and cannot resume or execute"
        )
    if not isinstance(value, dict) or set(value) != {
        "account_scope",
        "source_generation",
    }:
        raise ValueError(
            "Persistent allocation requires exact account/source admission"
        )
    if not isinstance(value["source_generation"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", value["source_generation"]
    ):
        raise ValueError("Persistent allocation source generation is invalid")
    account = value["account_scope"]
    if not isinstance(account, dict) or set(account) != {"path", "sha256"}:
        raise ValueError("Persistent allocation account pin is invalid")
    read_pinned_bytes(account, limit=128 * 1024)
    return value


def allocated_session(configuration, thread):
    """Read the actual native-created transcript; never invent an allocated ID."""
    import os
    import stat

    owner = allocation_binding(configuration)
    if (
        owner is None
        or not isinstance(thread, dict)
        or thread.get("ephemeral") is not False
        or not isinstance(thread.get("id"), str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", thread["id"])
        or thread.get("sessionId") != thread["id"]
        or thread.get("turns") != []
        or thread.get("cwd") != configuration["file_contract"]["scratch_root"]
        or thread.get("status", {}).get("type") != "idle"
        or any(
            thread.get(k) is not None
            for k in ("parentThreadId", "forkedFromId", "projectId")
        )
    ):
        raise ValueError(
            "Persistent allocation native readback is incomplete or differs"
        )
    path = Path(thread.get("path") or "")
    before = policy._path_identity(str(path))
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError("Allocated transcript must be its exact canonical native path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or not 1 <= info.st_size <= 64 * 1024 * 1024
        ):
            raise ValueError("Allocated transcript is not a bounded regular source")
        raw = b""
        while len(raw) < info.st_size:
            part = os.read(fd, min(1024 * 1024, info.st_size - len(raw)))
            if not part:
                break
            raw += part
        if (
            len(raw) != info.st_size
            or any(
                getattr(os.fstat(fd), k) != getattr(info, k)
                for k in (
                    "st_dev",
                    "st_ino",
                    "st_mode",
                    "st_nlink",
                    "st_uid",
                    "st_gid",
                    "st_size",
                    "st_mtime_ns",
                    "st_ctime_ns",
                )
            )
            or policy._path_identity(str(path)) != before
        ):
            raise ValueError("Allocated transcript changed during capture")
    finally:
        os.close(fd)
    value = {
        **deepcopy(owner),
        "session_id": thread["id"],
        "transcript": {
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
        },
    }
    resume_binding({**configuration, "resume": value})
    return value


def resume_binding(configuration, *, allow_growth=False):
    """Exact existing study-owned session; the parent still owns account admission.

    Pinned account artifact/source generation are not self-issued authorization.
    execute requires the current owner's revalidate callback before native effects.
    No history/path override, ephemeral substitution or new session is permitted.
    """
    from native_protection import read_pinned_bytes

    value = configuration.get("resume")
    if not isinstance(value, dict) or set(value) != {
        "session_id",
        "transcript",
        "account_scope",
        "source_generation",
    }:
        raise ValueError("Exact admitted resume binding required")
    if (
        not isinstance(value["session_id"], str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value["session_id"])
        or not isinstance(value["source_generation"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", value["source_generation"])
    ):
        raise ValueError("Resume session/source identity is invalid")
    account = value["account_scope"]
    if not isinstance(account, dict) or set(account) != {"path", "sha256"}:
        raise ValueError("Exact current account-scope artifact required")
    read_pinned_bytes(account, limit=128 * 1024)
    ref = value["transcript"]
    if (
        not isinstance(ref, dict)
        or set(ref) != {"path", "sha256", "size"}
        or type(ref["size"]) is not int
        or not 1 <= ref["size"] <= 64 * 1024 * 1024
    ):
        raise ValueError("Bounded exact native expense-window source required")
    path = Path(ref["path"])
    # Retained no-follow ancestry and one regular inode; compare only the admitted
    # prefix after resume, because the real owner intentionally appends history.
    before = policy._path_identity(str(path))
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError("Resume transcript aliases are not admitted")
    import os
    import stat

    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or (
                info.st_size < ref["size"]
                if allow_growth
                else info.st_size != ref["size"]
            )
        ):
            raise ValueError("Resume transcript size/type differs")
        raw = b""
        while len(raw) < ref["size"]:
            part = os.read(fd, min(1024 * 1024, ref["size"] - len(raw)))
            if not part:
                break
            raw += part
        if (
            hashlib.sha256(raw).hexdigest() != ref["sha256"]
            or policy._path_identity(str(path)) != before
        ):
            raise ValueError("Resume transcript prefix changed")
    finally:
        os.close(fd)
    first = raw.split(b"\n", 1)[0]
    header = json.loads(first)
    if (
        header.get("type") != "session_meta"
        or header.get("payload", {}).get("id") != value["session_id"]
    ):
        raise ValueError("Expense source is not the admitted native session")
    return value


def resume_thread(configuration, thread, *, before_resume=False):
    value = configuration["resume"]
    if (
        not isinstance(thread, dict)
        or thread.get("id") != value["session_id"]
        or thread.get("sessionId") != value["session_id"]
        or thread.get("ephemeral") is not False
        or thread.get("path") != value["transcript"]["path"]
        or thread.get("cwd") != configuration["file_contract"]["scratch_root"]
        or thread.get("status", {}).get("type")
        not in ({"idle", "notLoaded"} if before_resume else {"idle"})
        or thread.get("turns") != []
        or any(
            thread.get(k) is not None
            for k in ("parentThreadId", "forkedFromId", "projectId")
        )
    ):
        raise ValueError(
            "Resumed session must be the exact admitted idle persistent thread"
        )
    return thread


def _thread(configuration, response):
    policy.verify_active(configuration, response)
    thread = response.get("thread")
    if configuration.get("persistent_allocation") is True:
        allocated_session(configuration, thread)
        return thread
    if configuration.get("resume") is not None:
        return resume_thread(configuration, thread)
    if (
        not isinstance(thread, dict)
        or not isinstance(thread.get("id"), str)
        or not thread["id"]
        or len(thread["id"]) > 128
        or thread.get("sessionId") != thread["id"]
        or thread.get("ephemeral") is not True
        or thread.get("turns") != []
        or thread.get("cwd") != configuration["file_contract"]["scratch_root"]
        or any(
            thread.get(k) is not None
            for k in ("path", "parentThreadId", "forkedFromId", "projectId")
        )
    ):
        raise ValueError("Managed thread must be exactly isolated and unpersisted")
    return thread


def productive(configuration):
    return configuration.get("required_capabilities") not in (
        ["native-callback"],
        ["native-permission-probe"],
    )


def _base_effect_requests(configuration, sid):
    capabilities = configuration["required_capabilities"]
    if capabilities == ["native-callback"]:
        return []
    probe_id = 7 if configuration.get("resume") is not None else 5
    params = policy.probe_params(configuration)
    if capabilities == ["native-permission-probe"]:
        return [_rpc(probe_id, "command/exec", params)]
    transport = configuration.get("protection_observation", {}).get("transport", {})
    nonce = transport.get("connection_id")
    if not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise ValueError(
            "Productive probe requires the current owner connection binding"
        )
    params["processId"] = "synthesis-" + nonce
    probe = _rpc(probe_id, "command/exec", params)
    prompt = configuration.get("prompt")
    if (
        not isinstance(prompt, str)
        or not prompt
        or len(prompt.encode()) > 2 * 1024 * 1024
    ):
        raise ValueError("Managed model turn requires its exact admitted worker prompt")
    return [
        probe,
        _rpc(
            probe_id + 1,
            "config/read",
            {
                "cwd": configuration["file_contract"]["scratch_root"],
                "includeLayers": False,
            },
        ),
        _rpc(probe_id + 2, "thread/read", {"threadId": sid, "includeTurns": False}),
        _rpc(
            probe_id + 3,
            "turn/start",
            {
                "threadId": sid,
                "input": [{"type": "text", "text": prompt, "text_elements": []}],
                "model": configuration["selected"]["model"],
                "effort": configuration["selected"]["model_reasoning_effort"],
                "approvalPolicy": "never",
                "permissions": policy.validate(configuration["file_contract"])["id"],
            },
        ),
    ]


def effect_requests(configuration, sid):
    actions = _base_effect_requests(configuration, sid)
    if account_scope(configuration) is not None and productive(configuration):
        actions.insert(len(actions) - 1, account_request("before-turn"))
    return actions


def effect_request(configuration, sid):
    """The terminal action; all actual emission uses the complete owned plan."""
    actions = effect_requests(configuration, sid)
    return actions[-1] if actions else None


def command_result(value, request):
    if (
        not isinstance(value, dict)
        or set(value) != {"exitCode", "stdout", "stderr"}
        or type(value.get("exitCode")) is not int
        or any(not isinstance(value.get(k), str) for k in ("stdout", "stderr"))
        or sum(len(value[k].encode()) for k in ("stdout", "stderr"))
        > request["params"]["outputBytesCap"]
    ):
        raise ValueError(
            "Managed probe outcome exceeds its exact typed capture contract"
        )
    return value


def idle_thread(configuration, thread, expected):
    if configuration.get("resume") is not None:
        resume_thread(configuration, thread)
    else:
        if (
            not isinstance(thread, dict)
            or thread.get("status", {}).get("type") != "idle"
        ):
            raise ValueError("Managed productive session is not idle")
        # Reuse the admitted creation shape; no session/path substitution.
        left = {k: v for k, v in thread.items() if k != "status"}
        right = {k: v for k, v in expected.items() if k != "status"}
        if left != right:
            raise ValueError("Managed productive thread changed after probe")
    return thread


def protection_verdict(configuration, replies, probe_index, thread, turn_id):
    from native_protection import qualified
    from delegation_boundary import digest

    actions = effect_requests(configuration, thread["id"])
    capture = configuration.get("protection_observation", {})
    transport = capture.get("transport", {})
    if (
        not qualified(configuration, replies[probe_index]["result"])
        or capture.get("thread_id") != thread["id"]
        or transport.get("protocol") != STUDY_PROTOCOL
        or transport.get("probe_request_digest") != digest(actions[0])
        or transport.get("turn_id") != turn_id
        or not isinstance(capture.get("productive_after"), dict)
        or capture["productive_after"] != capture.get("after")
    ):
        raise ValueError(
            "Current productive connection protection is incomplete or differs"
        )
    return {
        "status": "ENFORCED",
        "mechanism": "codex-managed",
        "protocol": STUDY_PROTOCOL,
        "scope": "fixed filesystem/network controls and exact productive turn on this native connection/profile",
        "connection_id": transport["connection_id"],
        "thread_id": thread["id"],
        "turn_id": turn_id,
        "profile_digest": capture["profile_digest"],
        "probe_request_digest": transport["probe_request_digest"],
    }


def _readback(raw, configuration, request_raw, *, effect=True):
    from native_callback import _rows, hook_result, CallbackIncomplete

    rows, sent = _rows(raw), _rows(request_raw)
    native_sent = deepcopy(sent)
    account_ids = {"synthesis-account-before-session", "synthesis-account-before-turn"}
    if account_scope(configuration) is not None:
        labels = ["before-session"] + (
            ["before-turn"] if effect and productive(configuration) else []
        )
        for label in labels:
            expected_account = account_request(label)
            matched = [x for x in rows if x.get("id") == expected_account["id"]]
            if len(matched) != 1 or "error" in matched[0]:
                raise ValueError("Native account readback is missing or ambiguous")
            verify_account(configuration, matched[0].get("result"))
            position = next(i for i, row in enumerate(rows) if row is matched[0])
            before = (
                (3 if configuration.get("resume") is not None else 2)
                if label == "before-session"
                else (9 if configuration.get("resume") is not None else 7)
            )
            after = before + 1
            prior = [
                i
                for i, row in enumerate(rows)
                if type(row.get("id")) is int and row["id"] == before
            ]
            following = [
                i
                for i, row in enumerate(rows)
                if type(row.get("id")) is int and row["id"] == after
            ]
            if (
                len(prior) != 1
                or len(following) != 1
                or not prior[0] < position < following[0]
                or (
                    label == "before-turn"
                    and any(
                        row.get("method") in {"turn/started", "turn/completed"}
                        for row in rows[:position]
                    )
                )
            ):
                raise ValueError(
                    "Native account reply is outside its exact fresh native barriers"
                )
    elif any(x.get("id") in account_ids for x in rows):
        raise ValueError("Unadmitted native account readback")
    rows = [x for x in rows if x.get("id") not in account_ids]
    sent = [x for x in sent if x.get("id") not in account_ids]
    replies = [r for r in rows if "id" in r and "method" not in r]
    resuming = configuration.get("resume") is not None
    base_count = 6 if resuming else 4
    action_count = (
        0
        if not effect or configuration["required_capabilities"] == ["native-callback"]
        else (4 if productive(configuration) else 1)
    )
    expected_count = base_count + action_count
    if (
        len(replies) != expected_count
        or any(type(r.get("id")) is not int for r in replies)
        or [r["id"] for r in replies] != list(range(1, expected_count + 1))
        or any("error" in r or not isinstance(r.get("result"), dict) for r in replies)
    ):
        raise ValueError(
            "Managed native response sequence is incomplete, duplicated or failed"
        )
    expected = _base_requests(configuration, allow_resume_growth=True)
    policy.verify_config(configuration, replies[1]["result"])
    if resuming:
        resume_thread(
            configuration, replies[2]["result"].get("thread"), before_resume=True
        )
        thread = _thread(configuration, replies[3]["result"])
        policy.verify_config(configuration, replies[4]["result"])
        resume_thread(configuration, replies[5]["result"].get("thread"))
    else:
        thread = _thread(configuration, replies[2]["result"])
        policy.verify_config(configuration, replies[3]["result"])
    probe_index = base_count
    actions = _base_effect_requests(configuration, thread["id"]) if effect else []
    action = actions[-1] if actions else None
    expected.extend(actions)
    effect_index = expected_count - 1
    if actions:
        command_result(replies[probe_index]["result"], actions[0])
        if productive(configuration):
            policy.verify_config(configuration, replies[probe_index + 1]["result"])
            idle_thread(
                configuration, replies[probe_index + 2]["result"].get("thread"), thread
            )
    if (
        native_sent
        != requests(configuration, allow_resume_growth=True)
        + (effect_requests(configuration, thread["id"]) if effect else [])
        or sent != expected
    ):
        raise ValueError(
            "Managed native requests differ from exact admitted methods/arguments"
        )
    # An observed blocking hook cannot be ignored before dispatch. Genuine
    # Synthesis context delivery remains a separate mandatory source join.
    # Callback-only dialect forbids model work. In the separately admitted turn
    # path, validate typed work identity here and pass only callback notifications
    # to that decoder; its SessionStart/context checks stay unchanged.
    hook_rows = rows
    if action and action["method"] == "turn/start":
        turn_id = replies[effect_index]["result"].get("turn", {}).get("id")
        from native_codex_turn import transcript

        transcript(rows, thread["id"], turn_id)
        hook_rows = [
            row
            for row in rows
            if "method" not in row
            or row.get("method") == "thread/started"
            or (
                row.get("method", "").startswith("hook/")
                and row.get("params", {}).get("run", {}).get("eventName")
                == "sessionStart"
            )
        ]
    if resuming:
        hook_rows = [
            row for row in hook_rows if row.get("method", "").startswith("hook/")
        ]
        if hook_rows:
            hook_result(hook_rows, thread)
    else:
        hook_result(hook_rows, thread)
    terminal = "completed"
    if action and action["method"] == "command/exec":
        result = replies[effect_index]["result"]
        if (
            set(result) != {"exitCode", "stdout", "stderr"}
            or type(result["exitCode"]) is not int
            or any(not isinstance(result[k], str) for k in ("stdout", "stderr"))
            or sum(len(result[k].encode()) for k in ("stdout", "stderr"))
            > action["params"]["outputBytesCap"]
        ):
            raise ValueError(
                "Managed command outcome exceeds its typed capture contract"
            )
        terminal = "completed" if result["exitCode"] == 0 else "failed"
    elif action:
        turn = replies[effect_index]["result"].get("turn")
        if (
            not isinstance(turn, dict)
            or not isinstance(turn.get("id"), str)
            or not turn["id"]
        ):
            raise ValueError("Managed turn start lacks its native identity")
        ends = [r for r in rows if r.get("method") == "turn/completed"]
        if not ends:
            raise CallbackIncomplete("Managed native model turn has not completed")
        if len(ends) != 1:
            raise ValueError("Managed native turn completion is ambiguous")
        params = ends[0].get("params", {})
        done = params.get("turn", {})
        if (
            params.get("threadId") != thread["id"]
            or done.get("id") != turn["id"]
            or done.get("status") not in {"completed", "failed", "interrupted"}
        ):
            raise ValueError("Managed native turn completion identity differs")
        terminal = "completed" if done["status"] == "completed" else "failed"
    result = {
        "producer": "codex:" + thread["id"],
        "terminal": terminal,
        "usage": {"tokens": None, "usd_micros": None},
    }
    if configuration.get("persistent_allocation") is True:
        result["allocation"] = allocated_session(configuration, thread)
    if action and productive(configuration):
        result["protection"] = protection_verdict(
            configuration, replies, probe_index, thread, turn["id"]
        )
    return result


def parse(raw, configuration, request_raw):
    return _readback(raw, configuration, request_raw)


def execute(argv, configuration, cwd, timeout, environment, *, revalidate, resume=None):
    from native_callback import CallbackIncomplete

    if resume is not None:
        if configuration["required_capabilities"] in (
            ["native-callback"],
            ["native-permission-probe"],
        ):
            raise ValueError(
                "Existing session resume is only an admitted ordinary task"
            )
        configuration["resume"] = deepcopy(resume)
    contract = configuration["file_contract"]
    configuration.pop("protection_observation", None)
    if productive(configuration):
        import uuid

        configuration["protection_observation"] = {
            "transport": {
                "protocol": STUDY_PROTOCOL,
                "connection_id": uuid.uuid4().hex,
                "probe_request_digest": None,
                "turn_id": None,
            }
        }
    connection = None
    code, failure, raw, errors, sent = 2, None, b"", b"", b""
    cleanup = {"cleanup_verified": True, "scope": "No child started"}
    try:
        initial = policy.inspect(contract, executable=argv[0])
        if (
            argv != policy.server_argv(argv[0], contract)
            or configuration.get("executable_identity")
            != contract["permissions"]["profile"]["native_executable"]
        ):
            raise ValueError(
                "Managed invocation differs from its native identity/configuration"
            )
        revalidate()
        allocation_binding(configuration)
        if configuration.get("resume") is not None:
            resume_binding(configuration)
        connection = native_resume.MuseConnection(
            argv[0],
            cwd,
            timeout=timeout,
            max_bytes=MAX_BYTES,
            command=argv,
            environment={
                **environment,
                "SYNTHESIS_CALLBACK_OBSERVATION": "codex-ephemeral-callback",
            },
            require_jsonrpc=False,
        )

        def before_effect():
            revalidate()
            if policy.inspect(contract, executable=argv[0]) != initial:
                raise ValueError(
                    "Managed source changed at native transport write boundary"
                )
            if configuration.get("resume") is not None:
                resume_binding(configuration, allow_growth=True)
            allocation_binding(configuration)

        admit_effect = restrict_connection(
            connection, configuration, before_effect=before_effect
        )
        planned = _base_requests(configuration)
        connection.call("initialize", planned[0]["params"])
        connection.send(planned[1])
        policy.verify_config(
            configuration, connection.call("config/read", planned[2]["params"])
        )
        revalidate()
        if policy.inspect(contract, executable=argv[0]) != initial:
            raise ValueError(
                "Managed source or topology changed before thread creation"
            )
        if configuration.get("resume") is not None:
            resume_thread(
                configuration,
                connection.call("thread/read", planned[3]["params"]).get("thread"),
                before_resume=True,
            )
            revalidate()
            resume_binding(configuration)
            account_read(connection, configuration, "before-session")
            reply = connection.call("thread/resume", planned[4]["params"])
            thread = _thread(configuration, reply)
            policy.verify_config(
                configuration, connection.call("config/read", planned[5]["params"])
            )
            resume_thread(
                configuration,
                connection.call("thread/read", planned[6]["params"]).get("thread"),
            )
        else:
            if account_scope(configuration) is not None:
                account_read(connection, configuration, "before-session")
            reply = connection.call("thread/start", planned[3]["params"])
            thread = _thread(configuration, reply)
            policy.verify_config(
                configuration, connection.call("config/read", planned[4]["params"])
            )
        while True:
            try:
                _readback(
                    bytes(connection.raw_stdout),
                    configuration,
                    bytes(connection.raw_stdin),
                    effect=False,
                )
                break
            except CallbackIncomplete:
                connection._read()
        revalidate()
        if policy.inspect(contract, executable=argv[0]) != initial:
            raise ValueError(
                "Managed source or topology changed before admitted effect"
            )
        if configuration.get("resume") is not None:
            resume_binding(configuration, allow_growth=True)
        allocation_binding(configuration)
        actions = admit_effect(thread["id"])
        if actions:
            from native_protection import host_snapshot, qualified
            from delegation_boundary import digest

            before = host_snapshot(contract)
            revalidate()
            if policy.inspect(contract, executable=argv[0]) != initial:
                raise ValueError("Managed profile changed after positive controls")
            result = command_result(
                connection.call(actions[0]["method"], actions[0]["params"]), actions[0]
            )
            after = host_snapshot(contract, after=True)
            transport = configuration.get("protection_observation", {}).get("transport")
            configuration["protection_observation"] = {
                "before": before,
                "after": after,
                "thread_id": thread["id"],
                "profile_digest": digest(contract["permissions"]),
                "native_result_digest": digest(result),
            }
            if productive(configuration):
                transport["probe_request_digest"] = digest(actions[0])
                configuration["protection_observation"].update(
                    transport=transport, productive_after=None
                )
            if not qualified(configuration, result):
                raise ValueError("Actual managed protection controls did not pass")
            if productive(configuration):
                revalidate()
                if policy.inspect(contract, executable=argv[0]) != initial:
                    raise ValueError("Managed source changed after current probe")
                policy.verify_config(
                    configuration,
                    connection.call(actions[1]["method"], actions[1]["params"]),
                )
                idle_thread(
                    configuration,
                    connection.call(actions[2]["method"], actions[2]["params"]).get(
                        "thread"
                    ),
                    thread,
                )
                revalidate()
                if policy.inspect(contract, executable=argv[0]) != initial:
                    raise ValueError("Managed source changed before productive input")
                if configuration.get("resume") is not None:
                    resume_binding(configuration, allow_growth=True)
                if account_scope(configuration) is not None:
                    account_read(connection, configuration, "before-turn")
                started = connection.call(actions[-1]["method"], actions[-1]["params"])
                turn_id = started.get("turn", {}).get("id")
                if not isinstance(turn_id, str) or not turn_id:
                    raise ValueError("Managed productive turn has no native identity")
                transport["turn_id"] = turn_id
        productive_final = False
        while True:
            try:
                if productive(configuration) and not productive_final:
                    from native_callback import _rows

                    if any(
                        row.get("method") == "turn/completed"
                        for row in _rows(bytes(connection.raw_stdout))
                    ):
                        configuration["protection_observation"]["productive_after"] = (
                            host_snapshot(contract, after=True)
                        )
                        revalidate()
                        if policy.inspect(contract, executable=argv[0]) != initial:
                            raise ValueError(
                                "Managed source changed during productive work"
                            )
                        productive_final = True
                outcome = parse(
                    bytes(connection.raw_stdout),
                    configuration,
                    bytes(connection.raw_stdin),
                )
                if (
                    native_resume.binary_identity(argv[0])
                    != configuration["executable_identity"]
                ):
                    raise ValueError("Managed native executable changed")
                if configuration.get("resume") is not None:
                    resume_binding(configuration, allow_growth=True)
                code = 0 if outcome["terminal"] == "completed" else 2
                break
            except CallbackIncomplete:
                connection._read()
    except (OSError, ValueError, EOFError, TimeoutError, KeyError, TypeError) as exc:
        failure = str(exc)[:4096]
    except (KeyboardInterrupt, SystemExit) as exc:
        failure = "Managed native observation interrupted: " + type(exc).__name__
    finally:
        if connection:
            raw, errors, sent = (
                bytes(connection.raw_stdout),
                bytes(connection.stderr),
                bytes(connection.raw_stdin),
            )
            try:
                value = connection.close()
                cleanup = {
                    **value,
                    "cleanup_verified": value["group_absent"]
                    and value["leader_reaped"],
                }
            except (OSError, ValueError, KeyboardInterrupt, SystemExit) as exc:
                failure = failure or str(exc)
                cleanup = {**(connection.cleanup or {}), "cleanup_verified": False}
    if failure or not cleanup["cleanup_verified"]:
        code = 2
    return code, raw, errors, failure, cleanup, sent


def boundary(configuration, rows):
    """Replay only genuine authenticated owner observations, never caller PASS."""
    from native_protection import qualified

    unknown = {"status": "UNKNOWN", "mechanism": "codex-managed"}
    try:
        replies = [r for r in rows if type(r.get("id")) is int and "method" not in r]
        resuming = configuration.get("resume") is not None
        base = 6 if resuming else 4
        if configuration["required_capabilities"] == ["native-callback"]:
            return unknown
        thread = _thread(configuration, replies[3 if resuming else 2]["result"])
        sent = requests(configuration, allow_resume_growth=True) + effect_requests(
            configuration, thread["id"]
        )

        def encode(values):
            return ("".join(json.dumps(v) + "\n" for v in values)).encode()

        result = parse(encode(rows), configuration, encode(sent))
        if result["terminal"] != "completed":
            return unknown
        if productive(configuration):
            return result["protection"]
        if configuration.get("protection_observation", {}).get("thread_id") != thread[
            "id"
        ] or not qualified(configuration, replies[base]["result"]):
            return unknown
        return {
            "status": "ENFORCED",
            "mechanism": "codex-managed",
            "scope": "observed fixed filesystem/network controls on this native connection/profile only",
        }
    except (ValueError, OSError, KeyError, TypeError, IndexError):
        return unknown
