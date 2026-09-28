"""Model-free, ephemeral Codex callback observation through the native worker owner.

This does not execute a model turn, qualify recovery, copy trust or alter desktop
history. The existing PM worker admission and captured process receipt own it.
"""

from __future__ import annotations
import native_resume
from native_resume import MuseConnection
import native_codex

DIALECT = "codex.app_server_callback"
MAX_BYTES = 1024 * 1024


class CallbackIncomplete(ValueError):
    """No native readiness observation yet; finite owner may read more."""


def requests(configuration):
    if "permissions" in configuration["file_contract"]:
        from managed_native import requests as managed_requests

        return managed_requests(configuration)
    selected, contract = configuration["selected"], configuration["file_contract"]
    if any(
        not isinstance(selected.get(k), str) or not selected[k]
        for k in ("model", "model_reasoning_effort")
    ):
        raise ValueError(
            "Callback observation needs the actual selected model and effort"
        )
    return [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "clientInfo": {"name": "synthesis_callback_observer", "version": "1"},
                "capabilities": {"experimentalApi": False},
            },
        },
        {"jsonrpc": "2.0", "method": "initialized", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "thread/start",
            "params": {
                "cwd": contract["scratch_root"],
                "model": selected["model"],
                "approvalPolicy": "never",
                "sandbox": "workspace-write",
                "ephemeral": True,
                "config": {
                    "model_reasoning_effort": selected["model_reasoning_effort"],
                    "sandbox_workspace_write": {
                        "network_access": False,
                        "exclude_slash_tmp": True,
                        "exclude_tmpdir_env_var": True,
                        "writable_roots": contract["output_roots"],
                    },
                },
            },
        },
    ]


def _rows(raw):
    from native_resume import _decode_frame

    if (
        not isinstance(raw, bytes)
        or not raw
        or len(raw) > MAX_BYTES
        or not raw.endswith(b"\n")
    ):
        raise ValueError("Callback custody is missing, partial or oversized")
    rows = [_decode_frame(x) for x in raw.splitlines()]
    if len(rows) > 4096 or any(not isinstance(x, dict) for x in rows):
        raise ValueError("Callback frame inventory is invalid")
    return rows


def parse(raw, configuration, request_raw):
    if "permissions" in configuration["file_contract"]:
        from managed_native import parse as managed_parse

        return managed_parse(raw, configuration, request_raw)
    rows = _rows(raw)
    if _rows(request_raw) != requests(configuration):
        raise ValueError(
            "Callback requests differ; no turn, approval or extra request is admitted"
        )
    if (
        rows[0].get("id") != 1
        or type(rows[0].get("id")) is not int
        or not isinstance(rows[0].get("result"), dict)
    ):
        raise ValueError("Callback initialize response is absent")
    replies = [r for r in rows if "id" in r and "method" not in r]
    if (
        len(replies) != 2
        or [r.get("id") for r in replies] != [1, 2]
        or any("error" in r for r in replies)
    ):
        raise ValueError("Callback response identities are ambiguous or failed")
    response = replies[1].get("result")
    if not isinstance(response, dict) or not isinstance(response.get("thread"), dict):
        raise ValueError("Callback session response has no typed thread")
    thread = response["thread"]
    sid = thread.get("id")
    if (
        not isinstance(sid, str)
        or not sid
        or len(sid) > 128
        or thread.get("ephemeral") is not True
        or thread.get("path") is not None
        or thread.get("parentThreadId") is not None
        or thread.get("forkedFromId") is not None
        or thread.get("projectId") is not None
        or thread.get("sessionId") != sid
        or thread.get("turns") != []
        or thread.get("cwd") != configuration["file_contract"]["scratch_root"]
    ):
        raise ValueError("Callback thread is not an isolated unpersisted session")
    contract, selected = configuration["file_contract"], configuration["selected"]
    policy = response.get("sandbox", {})
    if (
        not isinstance(policy, dict)
        or response.get("cwd") != contract["scratch_root"]
        or response.get("approvalPolicy") != "never"
        or response.get("model") != selected["model"]
        or response.get("reasoningEffort") != selected["model_reasoning_effort"]
        or policy.get("type") != "workspaceWrite"
        or policy.get("networkAccess") is not False
        or policy.get("excludeSlashTmp") is not True
        or policy.get("excludeTmpdirEnvVar") is not True
        or not isinstance(policy.get("writableRoots"), list)
        or any(not isinstance(x, str) for x in policy["writableRoots"])
        or set(policy["writableRoots"]) != set(contract["output_roots"])
    ):
        raise ValueError("Native callback permission or selection readback differs")
    return hook_result(rows, thread)


def hook_result(rows, thread):
    sid = thread["id"]
    binding = {
        "producer": {"client": "codex", "thread_id": sid, "root_session_id": sid},
        "dialect": DIALECT,
        "mode": "native",
        "callback_thread": thread,
    }
    hooks = {}
    for row in rows:
        if "method" not in row:
            continue  # The enclosing owner validates each typed response.
        for fact in native_codex.decode_wire(row, binding):
            if fact["kind"] != "runtime.hook":
                continue
            value = fact["data"]
            key = value["hook_id"]
            if value["native_subtype"] == "hook_started":
                if key in hooks:
                    raise ValueError("Duplicate callback start")
                hooks[key] = [value]
            else:
                if key not in hooks or len(hooks[key]) != 1:
                    raise ValueError("Unpaired callback completion")
                start = hooks[key][0]["run"]
                end = value["run"]
                stable = (
                    "id",
                    "eventName",
                    "sourcePath",
                    "scope",
                    "source",
                    "executionMode",
                    "handlerType",
                    "startedAt",
                    "displayOrder",
                )
                if any(start[k] != end[k] for k in stable):
                    raise ValueError("Callback identity changed during execution")
                hooks[key].append(value)
    if not hooks or any(len(v) != 2 for v in hooks.values()):
        raise CallbackIncomplete("Callback execution is incomplete")
    if any(v[1]["outcome"] != "completed" for v in hooks.values()):
        raise ValueError("A synchronous callback failed or blocked")
    delivered = [
        v[1]
        for v in hooks.values()
        if any(
            e["kind"] == "context" and "SYNTHESIS_NATIVE_RECEIPT " in e["text"]
            for e in v[1]["entries"]
        )
    ]
    if not delivered:
        raise CallbackIncomplete("No delivered synthesis callback witness")
    if len(delivered) != 1:
        raise ValueError("Ambiguous delivered synthesis callback witnesses")
    return {
        "producer": "codex:" + sid,
        "terminal": "completed",
        "usage": {"tokens": None, "usd_micros": None},
    }


def execute(argv, configuration, cwd, timeout, environment):
    """One finite owner: initialize, ephemeral thread/start, paired callback, cleanup."""
    connection = None
    failure = None
    code = 2
    raw = b""
    errors = b""
    sent = b""
    cleanup = {"cleanup_verified": True, "scope": "No child started"}
    try:
        if native_resume.binary_identity(argv[0]) != configuration.get(
            "executable_identity"
        ):
            raise ValueError("Callback native executable differs from admitted launch")
        connection = MuseConnection(
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
        planned = requests(configuration)
        connection.call("initialize", planned[0]["params"])
        connection.send(planned[1])
        connection.call("thread/start", planned[2]["params"])
        while True:
            try:
                parse(
                    bytes(connection.raw_stdout),
                    configuration,
                    bytes(connection.raw_stdin),
                )
                if (
                    native_resume.binary_identity(argv[0])
                    != configuration["executable_identity"]
                ):
                    raise ValueError("Native executable changed during callback")
                code = 0
                break
            except CallbackIncomplete:
                # Native readiness is the actual completed paired callback, not elapsed idle.
                connection._read()
    except (OSError, ValueError, EOFError, TimeoutError) as exc:
        failure = str(exc)[:4096]
    except (KeyboardInterrupt, SystemExit) as exc:
        # Finish custody and owned cleanup; the failed result cannot be enrolled.
        failure = "Callback observation interrupted: " + type(exc).__name__
    finally:
        if connection:
            raw = bytes(connection.raw_stdout)
            errors = bytes(connection.stderr)
            sent = bytes(connection.raw_stdin)
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
