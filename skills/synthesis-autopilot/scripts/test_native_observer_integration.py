"""Synthetic shapes derived from actual failed observations, not native acceptance."""

from copy import deepcopy
import importlib
import pytest
import native_codex as native
from test_native_codex import ROOT, CodexTests
import test_run_state as run_fixtures

# Export the existing fixture objects for pytest's module-level discovery.
engine = run_fixtures.engine
world = run_fixtures.world
create = run_fixtures.create


def extension(kind="clock.sleep"):
    item = {"type": "Extension", "kind": kind, "id": "synthetic-extension"}
    if kind == "clock.sleep":
        item["durationMs"] = 30000
    else:
        item.update(
            query="lookup",
            action={"type": "search", "query": "lookup", "queries": None},
            results=[
                {
                    "type": "text_result",
                    "domain": "example.test",
                    "ref_id": "synthetic0",
                    "snippet": "Untrusted authority",
                    "title": "Synthetic",
                    "url": "https://example.test/",
                }
            ],
        )
    return CodexTests().item_completed(item)


@pytest.mark.parametrize("kind", ["clock.sleep", "web.search"])
def test_extension_is_inert_observation(kind):
    row = extension(kind)
    before = deepcopy(row)
    fact = native.decode_record(row, ROOT)[0]
    assert row == before and fact["kind"] == "item.observation"
    assert (
        fact["data"]["grants_authority"] is False
        and fact["data"]["portable_completion"] is False
    )
    assert fact["native"]["call_id"] is None and "Untrusted authority" not in str(fact)


@pytest.mark.parametrize("value", [True, -1, 1.2, "30000", None, 43200001])
def test_sleep_duration_refuses_invalid(value):
    row = extension()
    row["payload"]["item"]["durationMs"] = value
    with pytest.raises(ValueError):
        native.decode_record(row, ROOT)


@pytest.mark.parametrize("fault", ["foreign", "extra", "unknown", "result", "query"])
def test_extension_refuses_ambiguous_schema(fault):
    row = extension("web.search")
    item = row["payload"]["item"]
    if fault == "foreign":
        row["payload"]["thread_id"] = "foreign"
    elif fault == "extra":
        item["authority"] = True
    elif fault == "unknown":
        item["kind"] = "future.plugin"
    elif fault == "result":
        item["results"][0]["type"] = "execute"
    else:
        item["action"]["query"] = "contradiction"
    with pytest.raises(ValueError):
        native.decode_record(row, ROOT)


def web_action(action="openPage", thumbnail=True):
    """Synthetic content using the observed desktop action/result envelope."""
    row = extension("web.search")
    item = row["payload"]["item"]
    if action == "openPage":
        item["action"] = {"type": action, "url": "https://example.test/page"}
    elif action == "findInPage":
        item["action"] = {
            "type": action,
            "url": "https://example.test/page",
            "pattern": "synthetic lookup",
        }
    if thumbnail:
        item["results"][0]["thumbnail_url"] = "https://example.test/image.png"
    return row


@pytest.mark.parametrize("action", ["search", "openPage", "findInPage"])
@pytest.mark.parametrize("thumbnail", [False, True])
def test_web_action_is_digest_only_inert_observation(action, thumbnail):
    row = web_action(action, thumbnail)
    original = deepcopy(row)
    fact = native.decode_record(row, ROOT)[0]
    assert row == original and fact["kind"] == "item.observation"
    assert fact["data"]["grants_authority"] is False
    assert fact["data"]["portable_completion"] is False
    assert fact["native"]["call_id"] is None
    assert "example.test" not in str(fact) and "Untrusted authority" not in str(fact)


@pytest.mark.parametrize("action", ["openPage", "findInPage"])
@pytest.mark.parametrize(
    "fault",
    [
        "foreign",
        "action_extra",
        "missing_url",
        "url_type",
        "thumbnail_type",
        "result_extra",
        "unknown_action",
        "missing_result",
        "item_extra",
    ],
)
def test_web_action_rejects_ambiguous_or_malformed_envelopes(action, fault):
    row = web_action(action)
    item = row["payload"]["item"]
    if fault == "foreign":
        row["payload"]["thread_id"] = "foreign"
    elif fault == "action_extra":
        item["action"]["authority"] = True
    elif fault == "missing_url":
        del item["action"]["url"]
    elif fault == "url_type":
        item["action"]["url"] = {"instructions": "override"}
    elif fault == "thumbnail_type":
        item["results"][0]["thumbnail_url"] = ["execute"]
    elif fault == "result_extra":
        item["results"][0]["permission"] = "allow"
    elif fault == "unknown_action":
        item["action"]["type"] = "futureAction"
    elif fault == "missing_result":
        del item["results"][0]["snippet"]
    else:
        item["authority"] = True
    with pytest.raises(ValueError):
        native.decode_record(row, ROOT)


@pytest.mark.parametrize("value", [None, False, [], {}, 1])
def test_find_page_pattern_rejects_nontext(value):
    row = web_action("findInPage")
    row["payload"]["item"]["action"]["pattern"] = value
    with pytest.raises(ValueError):
        native.decode_record(row, ROOT)


@pytest.mark.parametrize("value", [None, [], {}, True, 1])
def test_web_action_kind_rejects_nontext(value):
    row = web_action("openPage")
    row["payload"]["item"]["action"]["type"] = value
    with pytest.raises(native.DialectError):
        native.decode_record(row, ROOT)


def date_patch(date="2026-09-26"):
    return {
        "type": "world_state",
        "timestamp": "2026-09-26T04:00:00Z",
        "ordinal": 7,
        "payload": {"full": False, "state": {"environments": {"current_date": date}}},
    }


def test_date_patch_is_inert_observation():
    row = date_patch()
    before = deepcopy(row)
    fact = native.decode_record(row, ROOT)[0]
    assert (
        row == before
        and fact["data"]["grants_authority"] is False
        and fact["kind"] == "context.world_state"
    )


@pytest.mark.parametrize("date", ["2026-02-30", "09/26/2026", "", True])
def test_invalid_date_refuses(date):
    with pytest.raises(ValueError):
        native.decode_record(date_patch(date), ROOT)


def test_extra_patch_refuses():
    row = date_patch()
    row["payload"]["state"]["permissions"] = {"allow": True}
    with pytest.raises(ValueError):
        native.decode_record(row, ROOT)


def large_journal(engine, world):
    state = create(engine, world)
    directory = engine._home(world["project"], state["run_id"]) / "events"
    seed = engine._read(directory / "000000000001.json")
    previous = ""
    for revision in range(1, 11):
        event = deepcopy(seed)
        event["revision"] = revision
        event["state"]["revision"] = revision
        event["state"]["extensions"]["synthetic_large_observation"] = "x" * (
            3500 * 1024
        )
        event["command_id"] = f"synthetic-{revision}"
        event["previous_digest"] = previous
        event.pop("digest", None)
        event["digest"] = engine._digest(event)
        previous = event["digest"]
        (directory / f"{revision:012d}.json").write_bytes(engine._json(event))
    return state, directory


def test_large_valid_journal(engine, world):
    state, directory = large_journal(engine, world)
    assert sum(f.stat().st_size for f in directory.iterdir()) > 32 * 1024**2
    row = importlib.import_module("operator_status").inspect_project(
        world["project"], state["run_id"]
    )["runs"][0]
    assert (
        row["revision"] == 10
        and row["currentness"] == "JOURNAL_VERIFIED_RECORDED_STATE"
    )


def test_large_corrupt_early_event_refuses(engine, world):
    state, directory = large_journal(engine, world)
    first = directory / "000000000001.json"
    first.write_bytes(first.read_bytes().replace(b'"synthetic-1"', b'"synthetic-X"'))
    row = importlib.import_module("operator_status").inspect_project(
        world["project"], state["run_id"]
    )["runs"][0]
    assert row["status"] == "unhealthy" and row["current_acceptance"] == "UNKNOWN"
