"""Hermes peer-captured hook observation grammar; only PM authenticates custody."""

from native_adapter_sdk import DialectError, bounded, fact, qualify, text

ADAPTER_VERSION = "hermes-observation-v1"
SURFACES = ("hermes-cli-shell-hooks",)
SUPPORTED_SCHEMAS = ("synthesis.hermes_observation.v1",)


def qualify_source(
    header,
    *,
    expected_root_session_id,
    expected_thread_id=None,
    expected_parent_thread_id=None,
    expected_agent_id=None,
):
    if (
        not isinstance(header, dict)
        or set(header)
        != {
            "type",
            "schema",
            "session_id",
            "producer_version",
            "capture_id",
            "selection_sha256",
        }
        or header.get("type") != "synthesis.hermes_observation"
        or type(header.get("schema")) is not int
        or header["schema"] != 1
    ):
        raise DialectError("not an owner-captured Hermes observation header")
    if expected_parent_thread_id is not None or expected_agent_id is not None:
        raise DialectError("Hermes callback cannot invent native child lineage")
    result = qualify(
        "hermes",
        header,
        session=text(header["session_id"]),
        version=text(header["producer_version"]),
        surface=SURFACES[0],
        schema=SUPPORTED_SCHEMAS[0],
        expected_root_session_id=expected_root_session_id,
        expected_thread_id=expected_thread_id,
    )
    result.update(
        capture_id=text(header["capture_id"]),
        selection_sha256=text(header["selection_sha256"]),
    )
    return result


def decode_record(row, producer, *, mode="synthetic", source_locator=None):
    bounded(row)
    if row.get("type") == "synthesis.hermes_observation":
        if (
            row.get("session_id") != producer["thread_id"]
            or row.get("capture_id") != producer["capture_id"]
            or row.get("selection_sha256") != producer["selection_sha256"]
        ):
            raise DialectError("Hermes observation identity changed")
        return []
    if (
        set(row) != {"payload", "result", "release", "peer", "sequence"}
        or type(row["sequence"]) is not int
        or row["sequence"] not in (0, 1)
    ):
        raise DialectError("invalid Hermes captured callback")
    payload = row["payload"]
    event = ("pre_llm_call", "pre_api_request")[row["sequence"]]
    if (
        payload.get("hook_event_name") != event
        or payload.get("session_id") != producer["thread_id"]
    ):
        raise DialectError("Hermes callback source or sequence differs")
    return [
        fact(
            "runtime.hook",
            "observed",
            {
                "native_subtype": event,
                "observation": row,
                "execution_authorized": False,
                "native_permissions": "UNKNOWN",
            },
            row,
            mode=mode,
            source_locator=source_locator,
            record_id=producer["capture_id"] + ":" + str(row["sequence"]),
            sequence=row["sequence"],
        )
    ]


def is_ignored_projection(projected, producer):
    return False


def record_sequences(row, producer):
    return {"capture": row["sequence"]} if "sequence" in row else {}
