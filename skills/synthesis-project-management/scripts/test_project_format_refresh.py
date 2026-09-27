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
