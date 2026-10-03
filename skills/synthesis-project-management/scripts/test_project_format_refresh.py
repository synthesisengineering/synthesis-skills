import json
import pytest
import project_format as fmt


def make_project(tmp_path):
    p = tmp_path / "demo"
    (p / "sessions").mkdir(parents=True)
    (p / "CONTEXT.md").write_text(
        "# Context\n\n## What's Next\n- [ ] Verify recovery\n- [x] Done\n````\n- [ ] example only\n````\n"
    )
    (p / "REFERENCE.md").write_text("# Reference\n")
    (p / "sessions/2026-09.md").write_text(
        "### 2026-09-25 — Earlier\n\n#### Details\n\n#### 2026-09-26 — Later\nTODO: inspect\n"
    )
    return p


def test_context_checkbox_candidates_have_provenance(tmp_path):
    p = make_project(tmp_path)
    fmt.migrate(p, apply=True)
    state = json.loads((p / fmt.STATE_NAME).read_text())
    loop = next(x for x in state["open_loops"] if x["text"] == "Verify recovery")
    assert loop["unverified"] is True and loop["owner"] == "unassigned"
    assert loop["source"]["path"] == "CONTEXT.md" and loop["source"]["line"] == 4
    assert not any(x["text"] in {"Done", "example only"} for x in state["open_loops"])


def test_all_heading_levels_and_no_fenced_headings(tmp_path):
    p = make_project(tmp_path)
    (p / "sessions/2026-09.md").write_text(
        "\n".join("#" * n + " 2026-09-26 session " + str(n) for n in range(1, 7))
        + "\n```\n## 2026-09-26 not a session\n```\n"
    )
    fmt.migrate(p, apply=True)
    index = (p / "sessions/INDEX.md").read_text()
    assert "(6 sessions)" in index and "not a session" not in index


def test_refresh_is_explicit_idempotent_and_preserves_curated_state(tmp_path):
    p = make_project(tmp_path)
    fmt.migrate(p, apply=True)
    state_path = p / fmt.STATE_NAME
    state = json.loads(state_path.read_text())
    state.update(
        goal="Curated goal",
        status="paused",
        last_brief="Human verified",
        skeleton=False,
    )
    state["open_loops"][0].update(owner="owner", unverified=False, text="Curated text")
    state["extra"] = {"preserve": True}
    state_path.write_text(json.dumps(state))
    (p / "sessions/2026-10.md").write_text(
        "##### 2026-10-01 New session\nOPEN: new candidate\n"
    )
    before = {f: f.read_bytes() for f in [state_path, p / "sessions/INDEX.md"]}
    report = fmt.refresh(p, apply=False)
    assert report["changed"] and all(f.read_bytes() == v for f, v in before.items())
    assert fmt.refresh(p, apply=True)["verified"]
    after = json.loads(state_path.read_text())
    assert (
        after["goal"] == "Curated goal"
        and after["status"] == "paused"
        and after["last_brief"] == "Human verified"
    )
    assert state["open_loops"][0] in after["open_loops"] and after["extra"] == {
        "preserve": True
    }
    assert after["last_session"] == "2026-10"
    bytes_once = {f: f.read_bytes() for f in before}
    mtimes = {f: f.stat().st_mtime_ns for f in before}
    assert fmt.refresh(p, apply=True)["changed"] == []
    assert all(
        f.read_bytes() == v and f.stat().st_mtime_ns == mtimes[f]
        for f, v in bytes_once.items()
    )


def test_refresh_refuses_symlink_and_invalid_state(tmp_path):
    p = make_project(tmp_path)
    fmt.migrate(p, apply=True)
    state = p / fmt.STATE_NAME
    state.write_text("{}")
    oldindex = (p / "sessions/INDEX.md").read_bytes()
    with pytest.raises(ValueError):
        fmt.refresh(p, apply=True)
    assert (p / "sessions/INDEX.md").read_bytes() == oldindex
    state.unlink()
    state.symlink_to(p / "REFERENCE.md")
    with pytest.raises(ValueError, match="symlink"):
        fmt.refresh(p, apply=True)


def test_refresh_recovers_after_one_atomic_output_write(tmp_path, monkeypatch):
    p = make_project(tmp_path)
    fmt.migrate(p, apply=True)
    (p / "sessions/2026-10.md").write_text("### 2026-10-01 New\nTODO: more work\n")
    state = p / fmt.STATE_NAME
    before = state.read_bytes()
    real = fmt._replace_generated
    calls = []

    def interrupt(path, text):
        calls.append(path)
        if len(calls) == 2:
            raise OSError("synthetic interruption after index write")
        real(path, text)

    monkeypatch.setattr(fmt, "_replace_generated", interrupt)
    with pytest.raises(OSError, match="interruption"):
        fmt.refresh(p, apply=True)
    assert "2026-10-01" in (p / "sessions/INDEX.md").read_text()
    assert state.read_bytes() == before
    monkeypatch.setattr(fmt, "_replace_generated", real)
    assert fmt.refresh(p, apply=True)["verified"]
    after = json.loads(state.read_text())
    assert after["last_session"] == "2026-10"
    assert len([x for x in after["open_loops"] if x["text"] == "more work"]) == 1
    assert fmt.refresh(p, apply=True)["changed"] == []


def test_checked_or_disappeared_candidate_is_not_silently_closed(tmp_path):
    p = make_project(tmp_path)
    fmt.migrate(p, apply=True)
    before = json.loads((p / fmt.STATE_NAME).read_text())["open_loops"]
    (p / "CONTEXT.md").write_text("# Context\n- [x] Verify recovery\n")
    fmt.refresh(p, apply=True)
    assert json.loads((p / fmt.STATE_NAME).read_text())["open_loops"] == before


def test_refresh_does_not_take_over_manual_index(tmp_path):
    p = make_project(tmp_path)
    fmt.migrate(p, apply=True)
    index = p / "sessions/INDEX.md"
    index.write_text("# Curated index\n")
    before = (p / fmt.STATE_NAME).read_bytes()
    with pytest.raises(ValueError, match="not generated"):
        fmt.refresh(p, apply=True)
    assert index.read_text() == "# Curated index\n"
    assert (p / fmt.STATE_NAME).read_bytes() == before


# Independent adversarial review controls.
@pytest.mark.parametrize(
    "text",
    [
        "# Context\n```text\n```not-a-closer\n- [ ] example\n```\n- [ ] actual\n",
        "# Context\n~~~~text\n~~~~not-a-closer\n- [ ] example\n~~~~\n- [ ] actual\n",
    ],
)
def test_fence_info_does_not_close_code_or_seed_tasks(tmp_path, text):
    p = make_project(tmp_path)
    (p / "CONTEXT.md").write_text(text)
    loops = fmt._skeleton_loops(None, p)
    assert [x["text"] for x in loops] == ["actual"]


def test_two_obligations_with_identical_wording_keep_both_provenances(tmp_path):
    p = make_project(tmp_path)
    (p / "CONTEXT.md").write_text(
        "# Context\n## Alpha\n- [ ] Validate result\n## Beta\n- [ ] Validate result\n"
    )
    loops = fmt._skeleton_loops(None, p)
    assert len(loops) == 2
    assert len({x["id"] for x in loops}) == 2
    assert [x["source"]["line"] for x in loops] == [3, 5]


def test_refresh_refuses_duplicate_state_fields_before_any_write(tmp_path):
    p = make_project(tmp_path)
    fmt.migrate(p, apply=True)
    state = p / fmt.STATE_NAME
    state.write_text(
        state.read_text().replace('"goal": "",', '"goal": "A", "goal": "B",')
    )
    before = {f: f.read_bytes() for f in [state, p / "sessions/INDEX.md"]}
    (p / "sessions/2026-10.md").write_text("### 2026-10-01 — later\n")
    with pytest.raises(ValueError, match="duplicate"):
        fmt.refresh(p, apply=True)
    assert all(f.read_bytes() == v for f, v in before.items())


def test_atomic_writer_persists_mode_and_renamed_parent(tmp_path, monkeypatch):
    import os
    import stat

    path = tmp_path / "record.md"
    path.write_text("before")
    path.chmod(0o640)
    real = fmt.os.fsync
    calls = []

    def tracked(fd):
        status = os.fstat(fd)
        calls.append((stat.S_ISDIR(status.st_mode), stat.S_IMODE(status.st_mode)))
        return real(fd)

    monkeypatch.setattr(fmt.os, "fsync", tracked)
    fmt._replace_generated(path, "after")
    assert calls == [(False, 0o640), (True, stat.S_IMODE(tmp_path.stat().st_mode))]
    assert path.read_text() == "after"
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


@pytest.mark.parametrize("line", [
    "We open the report.", "The OPEN item was discussed.", "open: this is prose",
    "We wrote TODO: an example.", "> TODO: quoted example", "`TODO: inline example`",
    "    TODO: indented code", "\tTODO: indented code", "- [x] TODO: completed example",
    "OPEN the report", "TODO:", "TODO:   ",
])
def test_session_markers_require_explicit_unquoted_marker_syntax(tmp_path, line):
    p = make_project(tmp_path)
    source = p / "sessions/2026-09.md"
    source.write_text(line + "\n\nTODO: actual\n")
    loops = fmt._skeleton_loops(source)
    assert [item["text"] for item in loops] == ["actual"]
    assert loops[0]["source"]["line"] == 3


@pytest.mark.parametrize("marker", ["TODO", "FIXME", "XXX", "OPEN", "TBD"])
@pytest.mark.parametrize("prefix", ["", "- ", "* ", "+ ", "1. ", "2) ", "   - "])
def test_explicit_session_markers_preserve_duplicate_occurrence_identity(tmp_path, marker, prefix):
    import hashlib
    p = make_project(tmp_path)
    source = p / "sessions/2026-09.md"
    original = prefix + marker + ": actual\n" + prefix + marker + ": actual\n"
    source.write_text(original)
    before = fmt._skeleton_loops(source)
    assert len(before) == 2
    assert len({item["id"] for item in before}) == 2
    assert all(item["text"] == "actual" and item["unverified"] for item in before)
    assert [item["source"]["line"] for item in before] == [1, 2]
    assert all(item["source"]["sha256"] == hashlib.sha256(original.encode()).hexdigest() for item in before)
    source.write_text("ordinary prose\n" + original)
    after = fmt._skeleton_loops(source)
    assert [item["id"] for item in after] == [item["id"] for item in before]
    assert [item["source"]["line"] for item in after] == [2, 3]


def test_marker_and_checkbox_examples_do_not_seed_obligations(tmp_path):
    p = make_project(tmp_path)
    source = p / "sessions/2026-09.md"
    source.write_text("```text\nTODO: fenced\n```\n> OPEN: quoted\n\nTODO: actual\n")
    (p / "CONTEXT.md").write_text("# Context\n> - [ ] quoted\n    - [ ] indented\n- [x] done\n- [ ] actual checkbox\n")
    loops = fmt._skeleton_loops(source, p)
    assert [item["text"] for item in loops] == ["actual", "actual checkbox"]


@pytest.mark.parametrize("body, expected", [
    ("> Quoted discussion\nTODO: quoted continuation\n\nOPEN: actual\n", ["actual"]),
    ("> Quoted discussion\nTODO: quoted continuation\n- OPEN: actual list\n", ["actual list"]),
    ("> Quoted discussion\nTODO: quoted continuation\n# Actual section\nOPEN: actual\n", ["actual"]),
])
def test_lazy_blockquote_marker_examples_remain_inert(tmp_path, body, expected):
    p = make_project(tmp_path)
    source = p / "sessions/2026-09.md"
    source.write_text(body)
    assert [x["text"] for x in fmt._skeleton_loops(source)] == expected


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_new_fenced_block_ends_lazy_quote_before_next_marker(tmp_path, fence):
    p = make_project(tmp_path)
    source = p / "sessions/2026-09.md"
    source.write_text("> Quoted paragraph\n" + fence + "text\nTODO: code\n" + fence + "\nTODO: actual\n")
    loops = fmt._skeleton_loops(source)
    assert [item["text"] for item in loops] == ["actual"]
    assert loops[0]["source"]["line"] == 5


@pytest.mark.parametrize("body", [
    "```\n> ```\nTODO: code\n```\nTODO: real\n",
    "> ```\n> > ```\n> TODO: code\n> ```\nTODO: real\n",
    "- item\n  ```\n  TODO: code\nTODO: real\n",
    "- item\n  - ```\n    TODO: code\nTODO: real\n",
])
def test_container_fence_coordinates_and_dedent(tmp_path, body):
    p = make_project(tmp_path)
    source = p / "sessions/2026-09.md"
    source.write_text(body)
    loops = fmt._skeleton_loops(source)
    assert [item["text"] for item in loops] == ["real"]
    assert loops[0]["source"]["line"] == body.splitlines().index("TODO: real") + 1


@pytest.mark.parametrize("body", [
    "- ```text\n  TODO: example\n  ```\n\nTODO: real\n",
    "1. ~~~text\n   OPEN: example\n   ~~~\n\nTODO: real\n",
    ">     quoted indented code\nTODO: real\n",
    "> ```text\n> example\n> ```\nTODO: real\n",
    "> quoted\n---\nTODO: real\n",
    "> quoted\n***\nTODO: real\n",
    "> quoted\n___\nTODO: real\n",
])
def test_commonmark_container_boundaries_preserve_real_marker(tmp_path, body):
    p = make_project(tmp_path)
    source = p / "sessions/2026-09.md"
    source.write_text(body)
    loops = fmt._skeleton_loops(source)
    assert [item["text"] for item in loops] == ["real"]
    assert loops[0]["source"]["line"] == body.splitlines().index("TODO: real") + 1


def test_migrate_refresh_list_fence_keeps_curated_candidates_and_coordinates(tmp_path):
    p = make_project(tmp_path)
    source = p / "sessions/2026-09.md"
    original = "- ```\n  TODO: example\n  ```\n\nTODO: real\n"
    source.write_text(original)
    assert fmt.migrate(p, apply=True)["verified"]
    path = p / fmt.STATE_NAME
    state = json.loads(path.read_text())
    assert {item["text"] for item in state["open_loops"]} == {"real", "Verify recovery"}
    real = next(item for item in state["open_loops"] if item["text"] == "real")
    assert real["source"]["line"] == 5
    real.update(owner="curated", unverified=False)
    state["goal"] = "Curated"
    path.write_text(json.dumps(state))
    source.write_text(original + "OPEN: next\n")
    assert fmt.refresh(p, apply=True)["verified"]
    after = json.loads(path.read_text())
    assert after["goal"] == "Curated" and real in after["open_loops"]
    assert "example" not in {item["text"] for item in after["open_loops"]}


@pytest.mark.parametrize("body", [
    "- > ```\n  > TODO: code\n  > ```\n\nTODO: real\n",
    "1. > ~~~\n   > TODO: code\n   > ~~~\n\nTODO: real\n",
    "- > quoted\n  TODO: lazy quote example\n\nTODO: real\n",
    "- > ```\n  > > ```\n  > TODO: code\n  > ```\nTODO: real\n",
])
def test_list_contained_quotes_remain_inert(tmp_path, body):
    p = make_project(tmp_path)
    source = p / "sessions/2026-09.md"
    source.write_text(body)
    loops = fmt._skeleton_loops(source)
    assert [item["text"] for item in loops] == ["real"]
    assert loops[0]["source"]["line"] == body.splitlines().index("TODO: real") + 1
