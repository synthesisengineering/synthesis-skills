"""BACKLOG B5: the web searches a session has made, against the principal's budget a session, before a research fan-out.

On 2026-09-23 six parallel research agents used up one session-wide web-search budget, each taking it for its own. The
principal's ruling: `synthesis searches [--agents N] [--session ID]` counts every search the session and its sub-agents
have made, from each harness's own records, says when the records cannot tell (never zero for that), and prints each of
N agents' share of what is left of `search_budget`, exiting 1 to refuse a fan-out whose share is under one search."""

import contextlib
import json
import os
from pathlib import Path

import pytest

from synthesis import approvals, cli, sessions

ROOT = Path(__file__).resolve().parents[1]
closed_to_us = pytest.mark.skipif(os.geteuid() == 0, reason="root reads and lists whatever the mode")


def _jsonl(path: Path, rows: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as out:
        out.write("".join(json.dumps(row) + "\n" for row in rows))
    return path


def _run(capsys, *words) -> tuple:
    code = cli.main(list(words))
    out, err = capsys.readouterr()
    return code, out, err


# --- Claude Code: `WebSearch` calls in the session's record and its sub-agents' -----------------------------------

def _claude(session: str, rows: list, *below: str, project: str = "-work") -> Path:
    """The session's own record, or with `below` a sub-agent's under its folder (`subagents/...`)."""
    folder = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / project
    return _jsonl(folder.joinpath(session, "subagents", *below) if below else folder / f"{session}.jsonl", rows)


def _calls(*calls, sidechain: bool = False) -> dict:
    """One assistant row with a tool call for each (tool, id)."""
    return {"type": "assistant", "isSidechain": sidechain, "cwd": "/work", "timestamp": "2026-11-18T10:00:00.000Z",
            "message": {"model": "claude-opus-5-5", "content": [
                {"type": "tool_use", "id": ident, "name": tool, "input": {"query": "release notes"}} for tool, ident in calls]}}


@pytest.fixture
def claude_session():
    """Session S1 with four searches: two of its own (one written twice), one by a sub-agent and one by a workflow's
    agent, one folder deeper; beside them a fetch, an MCP search tool, a request copy, a prompt that names the tool,
    a sub-agent's copy of its parent's call, a sub-agent's notes, and another session's search."""
    own = _claude("S1", [
        _calls(("WebSearch", "t1")),
        {"type": "user", "cwd": "/work", "timestamp": "2026-11-18T10:00:01.000Z", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "Web search results for query: release notes"}]}},
        _calls(("WebSearch", "t2"), ("WebFetch", "f1"), ("mcp__finder__web_search", "m1")),
        _calls(("WebSearch", "t2")),                                                   # the same call written again
        {"type": "api-request-blob", "message": {"content": [{"type": "tool_use", "id": "t7", "name": "WebSearch", "input": {}}]}},
        {"type": "user", "cwd": "/work", "timestamp": "2026-11-18T10:00:02.000Z",
         "message": {"role": "user", "content": "Use WebSearch sparingly."}},
    ])
    _claude("S1", [_calls(("WebSearch", "t1"), ("WebSearch", "t3"), sidechain=True)], "agent-a1.jsonl")
    (own.with_suffix("") / "subagents" / "agent-a1.meta.json").write_text('{"agentType": "research"}', encoding="utf-8")
    _claude("S1", [_calls(("WebSearch", "t4"), sidechain=True)], "workflows", "wf_1", "agent-a2.jsonl")
    _claude("S2", [_calls(("WebSearch", "t9"))])
    return own


def test_claude_code_counts_each_websearch_call_of_the_session_and_every_sub_agent_once(claude_session):
    found = sessions.searches("S1")
    assert (found["harness"], found["count"], found["agents"]) == ("claude-code", 4, 2)
    assert sessions.searches("S2")["count"] == 1 and sessions.searches("S2")["agents"] == 0


def test_the_session_is_read_where_its_prompt_hook_recorded_it(claude_session, tmp_path, monkeypatch):
    """The note the prompt hook keeps names the record even where this shell's environment names other folders."""
    approvals.remember("S1", str(claude_session))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "elsewhere"))
    assert sessions.searches("S1")["count"] == 4
    assert sessions.searches("S2")["count"] is None  # no note, and nothing where this environment looks


def test_with_no_budget_it_prints_the_count_says_no_budget_is_set_and_exits_0(claude_session, capsys, monkeypatch, write_config):
    monkeypatch.setenv("SYNTHESIS_SESSION", "S1")
    for config in ({}, {"search_budget": None}):
        write_config(config)
        code, out, err = _run(capsys, "searches", "--agents", "6")
        assert code == 0 and not err
        assert "session S1 (claude-code): 4 web searches made, read from its record and 2 of its sub-agents'" in out
        assert "no search budget is set" in out and "search_budget" in out and "share" not in out


def test_with_a_budget_it_prints_used_left_and_each_agents_share_rounded_down(claude_session, capsys, monkeypatch, write_config):
    monkeypatch.setenv("SYNTHESIS_SESSION", "S1")
    write_config({"search_budget": 20})
    code, out, err = _run(capsys, "searches", "--agents", "6")
    assert code == 0 and not err
    assert "budget: 20 web searches a session; 4 used, 16 left" in out
    assert "share: 2 web searches for each of 6 agents" in out          # 16 / 6, rounded down
    code, out, _ = _run(capsys, "searches")                             # one agent when none is named
    assert code == 0 and "share: 16 web searches for each of 1 agent" in out


def test_a_share_under_one_search_refuses_the_fan_out(claude_session, capsys, monkeypatch, write_config):
    monkeypatch.setenv("SYNTHESIS_SESSION", "S1")
    write_config({"search_budget": 6})
    code, out, err = _run(capsys, "searches", "--agents", "3")
    assert code == 1 and "4 used, 2 left" in out and "share: 0 web searches for each of 3 agents" in out
    assert err.startswith("refused: 2 web searches left, under one for each of 3 agents") and "dispatch at most 2" in err
    assert _run(capsys, "searches", "--agents", "2")[0] == 0


@pytest.mark.parametrize("budget", [4, 3, 0])
def test_a_budget_used_up_refuses_even_one_agent(claude_session, capsys, monkeypatch, write_config, budget):
    monkeypatch.setenv("SYNTHESIS_SESSION", "S1")
    write_config({"search_budget": budget})
    code, out, err = _run(capsys, "searches")
    assert code == 1 and "4 used, 0 left" in out and "share: 0 web searches for each of 1 agent" in out
    assert err.startswith(f"refused: none of the session's {budget} web searches is left") and "search_budget" in err


def test_the_session_is_named_before_or_after_the_command(claude_session, capsys, monkeypatch):
    monkeypatch.setenv("SYNTHESIS_SESSION", "S2")
    for words in (["--session", "S1", "searches"], ["searches", "--session", "S1"]):
        code, out, _ = _run(capsys, *words)
        assert code == 0 and out.startswith("session S1 (claude-code): 4 web searches made")
    assert _run(capsys, "searches")[1].startswith("session S2 (claude-code): 1 web search made")


@pytest.mark.parametrize("budget", ["20", 20.0, True, -1, [20], {"per_session": 20}])
def test_a_budget_that_is_no_whole_number_is_an_error_the_command_names(claude_session, capsys, monkeypatch, write_config, budget):
    monkeypatch.setenv("SYNTHESIS_SESSION", "S1")
    write_config({"search_budget": budget})
    code, out, err = _run(capsys, "searches", "--agents", "2")
    assert code == 2 and not out
    assert f"search_budget in {Path(os.environ['SYNTHESIS_HOME']) / 'config.json'} is {json.dumps(budget)}" in err
    assert "not a whole number of web searches" in err


def test_no_session_and_no_agents_are_errors(claude_session, capsys, monkeypatch):
    code, out, err = _run(capsys, "searches")
    assert code == 2 and not out and "no session id" in err
    monkeypatch.setenv("SYNTHESIS_SESSION", "S1")
    for agents in ("0", "-3"):
        code, out, err = _run(capsys, "searches", "--agents", agents)
        assert code == 2 and not out and "--agents" in err


def test_a_config_that_cannot_be_read_stops_the_count(claude_session, capsys, monkeypatch):
    monkeypatch.setenv("SYNTHESIS_SESSION", "S1")
    config = Path(os.environ["SYNTHESIS_HOME"]) / "config.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("{not json", encoding="utf-8")
    code, out, err = _run(capsys, "searches")
    assert code == 2 and not out and "the config cannot be read" in err


# --- when the records cannot tell: said, never zero ---------------------------------------------------------------

def test_a_session_this_mac_holds_no_record_of_cannot_tell(capsys, monkeypatch, write_config):
    found = sessions.searches("S404")
    assert found["count"] is None and found["why"] == "this Mac holds no record of it"
    monkeypatch.setenv("SYNTHESIS_SESSION", "S404")
    code, out, err = _run(capsys, "searches")
    assert code == 0 and "session S404: cannot tell how many web searches it made: this Mac holds no record of it" in out
    assert "no search budget is set" in out and "0 web searches" not in out
    write_config({"search_budget": 150})
    code, out, err = _run(capsys, "searches", "--agents", "3")
    assert code == 1 and "budget: 150 web searches a session; how many are used cannot be told" in out and "share" not in out
    assert err.startswith("refused: the searches made cannot be told, so no share of the 150 can be given")


@contextlib.contextmanager
def _closed(path: Path):
    was = path.stat().st_mode
    path.chmod(0)
    try:
        yield
    finally:
        path.chmod(was)


@closed_to_us
def test_a_sub_agent_folder_that_cannot_be_listed_or_a_record_that_cannot_be_read_cannot_tell(claude_session):
    folder = claude_session.with_suffix("") / "subagents" / "workflows"
    with _closed(folder):
        found = sessions.searches("S1")
    assert found["count"] is None and found["why"] == f"{folder} cannot be listed (Permission denied), and a record of it may be there"
    record = claude_session.with_suffix("") / "subagents" / "agent-a1.jsonl"
    with _closed(record):
        found = sessions.searches("S1")
    assert found["count"] is None and found["why"] == f"{record} cannot be read (Permission denied)"
    assert sessions.searches("S1")["count"] == 4


# --- Codex: each use of its hosted search tool, in the thread and its sub-agents' threads ------------------------

def _rollout(thread: str, at: str, rows: list, parent: str = "") -> Path:
    source = {"source": {"subagent": {"thread_spawn": {"parent_thread_id": parent}}}, "parent_thread_id": parent} if parent else {
        "source": "cli"}
    meta = {"type": "session_meta", "timestamp": "2026-11-18T10:00:00Z", "payload": {"id": thread, "cwd": "/work", **source}}
    folder = Path(os.environ["CODEX_HOME"]) / "sessions" / "2026" / "11" / "18"
    return _jsonl(folder / f"rollout-2026-11-18T{at}-{thread}.jsonl", [meta, *rows])


def _item(item: dict) -> dict:
    """Codex's event for a completed item: since mid-2026 the only record of a use of its search tool."""
    return {"type": "event_msg", "timestamp": "2026-11-18T10:00:05Z", "payload": {"type": "item_completed", "item": item}}


PARENT, CHILD, GRANDCHILD, OTHER = (f"01a1d000-0000-7000-8000-00000000000{n}" for n in range(1, 5))


@pytest.fixture
def codex_session():
    """The thread searched three times: a search recorded as an item and as a response item under one id, and a page
    its tool opened; a sub-agent's thread once, its own sub-agent once; another thread's search beside them, and an
    MCP tool named for search, a command and a function call that are no use of the tool."""
    own = _rollout(PARENT, "10-00-00", [
        _item({"type": "CommandExecution", "id": "exec-1", "command": ["/bin/zsh", "-lc", "ls"], "cwd": "/work"}),
        _item({"type": "WebSearch", "id": "ws_1", "query": "codex hooks", "action": {"type": "search", "query": "codex hooks"}}),
        {"type": "response_item", "timestamp": "2026-11-18T10:00:05Z", "payload": {"type": "web_search_call", "id": "ws_1", "status": "completed"}},
        _item({"type": "Extension", "kind": "web.search", "id": "exec-2", "query": "",
               "action": {"type": "openPage", "url": "https://example.com/hooks"}, "results": []}),
        _item({"type": "McpToolCall", "id": "m1", "server": "finder", "tool": "web_search", "arguments": {"query": "q"}}),
        {"type": "response_item", "timestamp": "2026-11-18T10:00:06Z", "payload": {
            "type": "function_call", "name": "exec_command", "call_id": "c1", "arguments": "{\"cmd\": \"echo web_search\"}"}},
    ])
    _rollout(CHILD, "10-05-00", [_item({"type": "Extension", "kind": "web.search", "id": "exec-3", "query": "q",
                                        "action": {"type": "search", "queries": ["q", "r"]}, "results": []})], parent=PARENT)
    _rollout(GRANDCHILD, "10-06-00", [_item({"type": "WebSearch", "id": "ws_4", "query": "q", "action": {"type": "search"}})],
             parent=CHILD)
    _rollout(OTHER, "10-07-00", [_item({"type": "WebSearch", "id": "ws_9", "query": "q", "action": {"type": "search"}})],
             parent="01a1d000-0000-7000-8000-000000000099")
    return own


def test_codex_counts_each_use_of_its_search_tool_in_the_thread_and_its_sub_agents_threads(codex_session):
    found = sessions.searches(PARENT)
    assert (found["harness"], found["count"], found["agents"]) == ("codex", 4, 2)
    assert (sessions.searches(CHILD)["count"], sessions.searches(CHILD)["agents"]) == (2, 1)


def test_a_codex_session_whose_records_hold_no_item_event_cannot_tell_unless_they_name_a_search(capsys, monkeypatch, write_config):
    talk = {"type": "response_item", "timestamp": "2026-11-18T10:00:01Z", "payload": {
        "type": "message", "role": "user", "content": [{"type": "input_text", "text": "Plan the web_search work."}]}}
    _rollout(PARENT, "10-00-00", [talk])
    found = sessions.searches(PARENT)
    assert found["count"] is None and found["harness"] == "codex"
    assert found["why"] == "none of its records holds an item event, where Codex records each use of its search tool"
    monkeypatch.setenv("SYNTHESIS_SESSION", PARENT)
    code, out, _ = _run(capsys, "searches")
    assert code == 0 and f"session {PARENT} (codex): cannot tell how many web searches it made: none of its records" in out
    write_config({"search_budget": 40})
    assert _run(capsys, "searches")[0] == 1
    _rollout(CHILD, "10-00-00", [{"type": "response_item", "timestamp": "2026-11-18T10:00:05Z",
                                  "payload": {"type": "web_search_call", "id": "ws_1", "status": "completed"}}])
    assert sessions.searches(CHILD)["count"] == 1  # an older rollout named its searches as response items alone


# --- Muse: its client tool `web_search`, in the session's record and its sub-agents' ----------------------------

def _muse(rows: list, *agent: str) -> Path:
    folder = Path(os.environ["XDG_DATA_HOME"]) / "muse" / "sessions" / "2026" / "11" / "18" / "M1"
    return _jsonl(folder.joinpath("subagent", agent[0], "session.jsonl") if agent else folder / "session.jsonl", rows)


def _mode(mode) -> dict:
    return {"payload_type": "runtime.session.metadata", "recorded_at": 1795000000000000,
            "payload": {"kind": "metadata", "record": {"workspace_root": "/work", "web_search_mode": mode}}}


def _muse_calls(*calls) -> dict:
    return {"payload_type": "runtime.session", "recorded_at": 1795000001000000, "payload": {"kind": "run", "event": {
        "kind": "assistant_tool_calls_committed", "tool_calls": [{"call_id": i, "name": n, "args": "{}"} for n, i in calls]}}}


def test_muse_counts_its_web_search_calls_with_its_sub_agents_in_the_client_mode():
    _muse([_mode("client"), _muse_calls(("web_search", "k1"), ("read_file", "k2"), ("search", "k3")), _muse_calls(("web_search", "k4"))])
    _muse([_muse_calls(("web_search", "k5"), ("web_fetch", "k6"))], "A1")       # a sub-agent inherits the mode
    found = sessions.searches("M1")
    assert (found["harness"], found["count"], found["agents"]) == ("muse", 3, 1)


@pytest.mark.parametrize("own, agents, why", [
    ([_mode("provider")], [], "its records name the web search mode 'provider', and only in the client mode does Muse "
                              "record each search as a call of its own"),
    ([_mode("client")], [_mode("provider")], "its records name the web search mode 'provider', and only in the client "
                                             "mode does Muse record each search as a call of its own"),
    ([], [], "its record names no web search mode, and only in the client mode does Muse record each search as a call of its own"),
])
def test_muse_cannot_tell_outside_the_client_mode_or_where_no_mode_is_named(own, agents, why):
    _muse(own + [_muse_calls(("web_search", "k1"))])
    if agents:
        _muse(agents, "A1")
    found = sessions.searches("M1")
    assert found["count"] is None and found["why"] == why


# --- the fan-out rule and the config reference ----------------------------------------------------------------

def test_the_fan_out_rule_runs_the_count_before_dispatch_and_briefs_each_share():
    fan_out = (ROOT / "skills" / "synthesis-autopilot" / "references" / "delegation.md").read_text(encoding="utf-8").split(
        "\n## Sub-Agent Fan-Out Hygiene\n")[1].split("\n## ")[0]
    rule = next(line for line in fan_out.splitlines() if line.startswith("4. **Allocate shared budgets in the brief.**"))
    assert "run `synthesis searches --agents N`" in rule and "`search_budget`" in rule and "brief" in rule
    assert "exiting 1" in rule and "SYNTHESIS_SEARCH_BUDGET_PER_AGENT" in rule  # added to, never trimmed
    keys = (ROOT / "skills" / "synthesis-agent-guardrails" / "references" / "config.md").read_text(encoding="utf-8").split(
        "\n## Keys\n")[1].split("\n## ")[0]
    row = next(line for line in keys.splitlines() if line.startswith("| `search_budget` |"))
    assert "`synthesis searches --agents N`" in row and "exits 1" in row
