"""Archival preserves old evidence through one lease CAS, using real Git fixtures."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import pytest
import coordination as c
import coordination_archive as a

NOW = datetime(2026, 9, 16, 14, 0, tzinfo=timezone.utc)


def session(name, heartbeat="2026-07-01T10:00:00+00:00", status="released"):
    identity = c.new_identity([], legacy_id=name)
    return c.Session(identity.session_uuid, identity.compact_id, identity.speakable_id,
                     name, "fixture", "fixture", "fixture", heartbeat, heartbeat,
                     "implementation", [], "fixture", [], "contributor", status)


def message(sender, recipient, stamp="2026-07-02T10:00:00+00:00", body="Exact evidence.\n"):
    return f"### → {recipient}, from {sender} — {stamp}\n\n{body}\n"


def content(sessions, messages=""):
    text = c.replace_table(c.template(), sessions)
    boundary = text.index("---\n\n## Protocol")
    return text[:boundary] + messages + text[boundary:]


@pytest.fixture
def leased(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(remote)], check=True)
    board = tmp_path / "machine" / "active-sessions.md"
    board.parent.mkdir()
    (board.parent / "lease.json").write_text(json.dumps({"remote": str(remote)}))
    return board


def seed(board, text):
    c.locked_update(board, lambda _: text)


def test_split_preserves_active_recent_ambiguous_and_broadcast_bytes():
    old, other = session("old"), session("other")
    active, recent = session("active", status="active"), session("recent", "2026-09-01T00:00:00+00:00")
    moved = message(old.label, other.label, body="Unicode α and | table bytes.\n")
    retained = (message(old.label, active.label) + message(old.label, "all") +
                message(old.label, "unknown") + message("unknown", other.label))
    original = content([old, other, active, recent], moved + retained)
    plan = a.plan_archive(original, {}, now=NOW)
    assert [r.id for r in c.rows(plan.board)] == [active.id, recent.id]
    assert retained in plan.board and moved not in plan.board
    entries = a.decode_month("2026-07.md", plan.months["2026-07.md"])
    assert [x["payload"] for x in entries if x["kind"] == "message"] == [moved]
    assert plan.rows == 2 and plan.messages == 1
    assert a.plan_archive(plan.board, plan.months, now=NOW).months == plan.months


@pytest.mark.parametrize("heartbeat", ["unknown", "2026-07-01", "2027-01-01T00:00:00+00:00", "2026-08-17T14:00:00+00:00"])
def test_unknown_naive_future_and_exact_cutoff_rows_retained(heartbeat):
    original = content([session("old", heartbeat)])
    plan = a.plan_archive(original, {}, now=NOW)
    assert plan.board == original and not plan.months


def test_archived_identity_can_complete_a_later_message_archive():
    old, later = session("old"), session("later", "2026-09-01T00:00:00+00:00")
    msg = message(old.label, later.label)
    first = a.plan_archive(content([old, later], msg), {}, now=NOW)
    assert msg in first.board
    second = a.plan_archive(first.board, first.months, now=datetime(2026, 11, 1, tzinfo=timezone.utc))
    assert msg not in second.board and second.messages == 1


def test_duplicate_messages_keep_multiplicity():
    old = session("old")
    msg = message(old.label, old.label)
    plan = a.plan_archive(content([old], msg * 2), {}, now=NOW)
    entries = a.decode_month("2026-07.md", plan.months["2026-07.md"])
    assert len([x for x in entries if x["kind"] == "message"]) == 2


def test_real_cas_retains_archive_as_reachable_second_parent_and_one_file_tree(leased):
    seed(leased, content([session("old")]))
    result = a.archive(leased, now=NOW)
    config = c.lease_configuration(leased)
    tip, text = c.lease_fetch(config)
    archive = a.archive_oid(text)
    repo = c.lease_repository(config)
    parents = c.git_lease(repo, "rev-list", "--parents", "-n", "1", tip).stdout.split()
    assert len(parents) == 3 and parents[2] == archive
    assert c.git_lease(repo, "ls-tree", "--name-only", tip).stdout.split() == [leased.name]
    assert a.load_months(config, tip, text) == {"2026-07.md": (leased.parent / "active-sessions.archive/2026-07.md").read_text()}
    assert result["rows"] == 1
    # Existing writer API must preserve the referenced archive through ancestry.
    c.locked_update(leased, lambda board: board.replace("# Synthesis", "# Revised Synthesis", 1), require_fence=True)
    new_tip, new_text = c.lease_fetch(config)
    assert a.load_months(config, new_tip, new_text)
    assert a.archive(leased, now=NOW)["rows"] == 0


def test_failed_publication_preserves_local_board_and_no_archive_mirror(leased, monkeypatch):
    seed(leased, content([session("old")]))
    before = leased.read_bytes()
    monkeypatch.setattr(c, "lease_publish", lambda *args, **kwargs: (False, "fixture refusal"))
    with pytest.raises(RuntimeError, match="compare-and-swap"):
        a.archive(leased, now=NOW)
    assert leased.read_bytes() == before
    assert not (leased.parent / "active-sessions.archive").exists()


def test_cas_retry_replans_against_competing_board(leased, monkeypatch):
    old, late = session("old"), session("late", status="active")
    seed(leased, content([old]))
    original = c.lease_publish
    raced = False
    def publish(config, name, text, expected, **kwargs):
        nonlocal raced
        if not raced:
            raced = True
            fresh = c.ensure_lease_declaration(content([old, late]), config["remote"])
            assert original(config, name, fresh, expected)[0]
        return original(config, name, text, expected, **kwargs)
    monkeypatch.setattr(c, "lease_publish", publish)
    a.archive(leased, now=NOW)
    assert [r.id for r in c.rows(leased.read_text())] == [late.id]
    months = a.load_months(c.lease_configuration(leased), *c.lease_fetch(c.lease_configuration(leased)))
    assert len(a.decode_month("2026-07.md", months["2026-07.md"])) == 1


def test_missing_unreachable_archive_refuses_without_board_change(leased):
    seed(leased, "Archive: " + "0" * 40 + "\n" + content([session("old")]))
    before = leased.read_bytes()
    with pytest.raises(RuntimeError, match="archive"):
        a.archive(leased, now=NOW)
    assert leased.read_bytes() == before


def test_mirror_hydration_after_post_publish_crash(leased, monkeypatch):
    seed(leased, content([session("old")]))
    real = a.hydrate
    monkeypatch.setattr(a, "hydrate", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("crash")))
    with pytest.raises(OSError, match="crash"):
        a.archive(leased, now=NOW)
    monkeypatch.setattr(a, "hydrate", real)
    result = a.archive(leased, now=NOW)
    assert result["rows"] == 0 and not c.rows(leased.read_text())
    assert (leased.parent / "active-sessions.archive/2026-07.md").is_file()


@pytest.mark.parametrize("kind", ["directory_symlink", "file_symlink", "modified"])
def test_foreign_mirror_content_is_not_overwritten(leased, tmp_path, kind):
    seed(leased, content([session("old")]))
    destination = leased.parent / "active-sessions.archive"
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    if kind == "directory_symlink":
        destination.symlink_to(foreign, target_is_directory=True)
    else:
        destination.mkdir()
        if kind == "file_symlink":
            (foreign / "data").write_text("retained")
            (destination / "2026-07.md").symlink_to(foreign / "data")
        else:
            (destination / "2026-07.md").write_text("retained")
    before = leased.read_bytes()
    with pytest.raises((ValueError, RuntimeError), match="archive"):
        a.archive(leased, now=NOW)
    assert leased.read_bytes() == before


def test_unleased_write_before_remove_recovers_idempotently(tmp_path, monkeypatch):
    board = tmp_path / "active-sessions.md"
    board.write_text(content([session("old")]))
    original = c.write_board
    monkeypatch.setattr(c, "write_board", lambda *args: (_ for _ in ()).throw(OSError("crash")))
    with pytest.raises(OSError, match="crash"):
        a.archive(board, now=NOW)
    assert len(c.rows(board.read_text())) == 1
    monkeypatch.setattr(c, "write_board", original)
    a.archive(board, now=NOW)
    month = (tmp_path / "active-sessions.archive/2026-07.md").read_text()
    assert len(a.decode_month("2026-07.md", month)) == 1
    assert not c.rows(board.read_text())


def test_dry_run_never_mutates_local_artifacts(leased):
    seed(leased, content([session("old")]))
    before = leased.read_bytes()
    result = a.archive(leased, now=NOW, dry_run=True)
    assert result["rows"] == 1 and leased.read_bytes() == before
    assert not (leased.parent / "active-sessions.archive").exists()


def test_unknown_heading_inside_native_message_preserves_entire_body():
    old = session("old")
    msg = message(old.label, old.label, body="Keep this whole body.\n### → legacy, from old — no date\ntrailing evidence\n")
    original = content([old], msg)
    plan = a.plan_archive(original, {}, now=NOW)
    assert msg in plan.board and plan.messages == 0


def test_reactivated_archived_identity_remains_a_live_message_recipient():
    old, other = session("old"), session("other")
    first = a.plan_archive(content([old]), {}, now=NOW)
    old.status = "active"
    msg = message(other.label, old.label)
    second = a.plan_archive(content([other, old], msg), first.months, now=NOW)
    assert msg in second.board and second.messages == 0


def test_archive_tree_rejects_path_or_mode_changes(leased):
    seed(leased, content([session("old")]))
    config = c.lease_configuration(leased)
    tip, text = c.lease_fetch(config)
    blob = a.checked(config, "hash-object", "-w", "--stdin", input_text="retained").strip()
    tree = a.checked(config, "mktree", input_text=f"120000 blob {blob}\t2026-07.md\n").strip()
    oid = a.checked(config, "commit-tree", tree, "-m", "fixture").strip()
    assert c.lease_publish(config, leased.name, a.set_archive_oid(text, oid), tip, archive_parent=oid)[0]
    with pytest.raises(RuntimeError, match="archive tree"):
        a.archive(leased, now=NOW)


def test_archive_commit_existing_but_unreachable_is_refused(leased):
    seed(leased, content([session("old")]))
    config = c.lease_configuration(leased)
    tip, text = c.lease_fetch(config)
    plan = a.plan_archive(text, {}, now=NOW)
    oid = a.commit_months(config, plan.months, None)
    assert c.lease_publish(config, leased.name, a.set_archive_oid(text, oid), tip)[0]
    with pytest.raises(RuntimeError, match="archive Git"):
        a.archive(leased, now=NOW)


def test_fresh_machine_hydrates_monthly_history_from_same_remote(leased, tmp_path):
    seed(leased, content([session("old")]))
    a.archive(leased, now=NOW)
    second = tmp_path / "second" / "active-sessions.md"
    second.parent.mkdir()
    (second.parent / "lease.json").write_bytes((leased.parent / "lease.json").read_bytes())
    a.archive(second, now=NOW)
    assert (second.parent / "active-sessions.archive/2026-07.md").read_bytes() == (leased.parent / "active-sessions.archive/2026-07.md").read_bytes()


def test_unleased_journal_divergence_preserves_new_board_and_journal(tmp_path, monkeypatch):
    board = tmp_path / "active-sessions.md"
    board.write_text(content([session("old")]))
    original = c.write_board
    monkeypatch.setattr(c, "write_board", lambda *args: (_ for _ in ()).throw(OSError("crash")))
    with pytest.raises(OSError):
        a.archive(board, now=NOW)
    monkeypatch.setattr(c, "write_board", original)
    current = content([session("new", status="active")])
    board.write_text(current)
    with pytest.raises(RuntimeError, match="diverged"):
        a.archive(board, now=NOW)
    assert board.read_text() == current
    assert (tmp_path / ".active-sessions.archive-journal.json").exists()


def test_cli_exposes_dry_run(tmp_path):
    board = tmp_path / "active-sessions.md"
    original = content([session("old")])
    board.write_text(original)
    args = c.parser().parse_args(["--board", str(board), "archive", "--dry-run", "--json"])
    assert c.COMMANDS[args.command](args) == 0
    assert board.read_text() == original


@pytest.mark.parametrize("fence", ["```markdown", "~~~~", "   ```"])
def test_fenced_quoted_message_never_truncates_live_recipient(fence):
    old, other, live = session("old"), session("other"), session("live", status="active")
    closing = "~~~~" if "~" in fence else "```"
    quoted = message(old.label, other.label) + closing + "\nACTION FOR ACTIVE OWNER\n"
    msg = message(old.label, live.label, body=f"Quoted exchange:\n{fence}\n{quoted}")
    plan = a.plan_archive(content([old, other, live], msg), {}, now=NOW)
    assert msg in plan.board and plan.messages == 0


def test_directory_durability_precedes_row_removal_and_journal_unlink(tmp_path, monkeypatch):
    import stat
    board = tmp_path / "active-sessions.md"
    board.write_text(content([session("old")]))
    events = []
    fsync, write_board, unlink = a.os.fsync, c.write_board, Path.unlink
    def sync(fd):
        events.append("directory" if stat.S_ISDIR(a.os.fstat(fd).st_mode) else "file")
        return fsync(fd)
    def write(path, data):
        assert events.count("directory") >= 3
        events.append("board")
        return write_board(path, data)
    def remove(path, *args, **kwargs):
        if path.name == ".active-sessions.archive-journal.json":
            assert events[-1] == "directory" and "board" in events
            events.append("journal_unlink")
        return unlink(path, *args, **kwargs)
    monkeypatch.setattr(a.os, "fsync", sync)
    monkeypatch.setattr(c, "write_board", write)
    monkeypatch.setattr(Path, "unlink", remove)
    a.archive(board, now=NOW)
    assert events[-1] == "directory"


def test_recent_administrative_record_is_never_absorbed_into_old_message():
    old, other = session("old"), session("other")
    text = content([old, other], message(old.label, other.label))
    text = c._append_administrative_release(text, old, "retain exact audit", "fixture-operator")
    plan = a.plan_archive(text, {}, now=NOW)
    assert "retain exact audit" in plan.board and "recorded-administrative-release" in plan.board
    assert plan.messages == 0
