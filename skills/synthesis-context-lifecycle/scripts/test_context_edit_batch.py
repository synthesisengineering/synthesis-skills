import json
from pathlib import Path
import pytest
import context_edit as editor
import context_edit as edit


def test_entire_table_without_trailing_newline():
    table = "| A | B |\n| --- | --- |\n| a | b |"
    assert (
        editor.apply_replacement(table + "\n", table, "Replacement") == "Replacement\n"
    )
    assert (
        editor.apply_replacement(
            table.replace("\n", "\r\n") + "\r\n",
            table.replace("\n", "\r\n"),
            "Replacement",
        )
        == "Replacement\r\n"
    )


def test_partial_table_remains_protected():
    with pytest.raises(editor.ContextEditError, match="table"):
        editor.apply_replacement(
            "| A | B |\n| --- | --- |\n| a | b |\n", "| --- | --- |", "broken"
        )


def test_file_flags_preserve_exact_bytes(tmp_path):
    target = tmp_path / "note.md"
    target.write_bytes(b"old\r\n")
    anchor = tmp_path / "anchor"
    anchor.write_bytes(b"old\r\n")
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"new\r\n")
    assert (
        editor.main(
            [
                "replace",
                "--file",
                str(target),
                "--anchor-file",
                str(anchor),
                "--replacement-file",
                str(replacement),
            ]
        )
        == 0
    )
    assert target.read_bytes() == b"new\r\n"
    anchor.write_bytes(b"new\r\n")
    replacement.write_bytes(b"prefix\r\n")
    assert (
        editor.main(
            [
                "insert-before",
                "--file",
                str(target),
                "--anchor-file",
                str(anchor),
                "--text-file",
                str(replacement),
            ]
        )
        == 0
    )
    assert target.read_bytes() == b"prefix\r\nnew\r\n"


def test_batch_final_budget_and_currency_once(tmp_path, monkeypatch):
    target = tmp_path / "CONTEXT.md"
    original = (
        "**Phase:** Round 1\n**Last session:** 2026-09-26 Round 1\nkeep\nremove\n"
    )
    target.write_text(original)
    calls = []
    real = editor._atomic_write
    monkeypatch.setattr(
        editor, "_atomic_write", lambda *a: (calls.append(a), real(*a))[1]
    )
    edits = [
        {"op": "set-field", "field": "Phase", "value": "Round 2"},
        {"op": "insert-before", "anchor": "keep", "text": "new\n"},
        {"op": "delete-line", "anchor": "remove"},
        {"op": "set-field", "field": "Last session", "value": "2026-09-26 Round 2"},
    ]
    result = editor.apply_edits(target, edits, max_lines=4)
    assert result["changed"] and len(calls) == 1
    assert (
        target.read_text()
        == "**Phase:** Round 2\n**Last session:** 2026-09-26 Round 2\nnew\nkeep\n"
    )


@pytest.mark.parametrize(
    "edits",
    [
        [
            {"op": "replace", "anchor": "old", "replacement": "new"},
            {"op": "replace", "anchor": "missing", "replacement": "x"},
        ],
        [{"op": "replace", "anchor": "old", "replacement": "new"}, {"op": "bad"}],
        [{"op": "replace", "anchor": "old", "replacement": "new", "count": True}],
        [{"op": "replace", "anchor": "old", "replacement": "new", "file": "elsewhere"}],
        [],
        {"edits": []},
    ],
)
def test_batch_preflight_refuses_without_write(tmp_path, edits):
    target = tmp_path / "note.md"
    target.write_text("old\n")
    with pytest.raises(editor.ContextEditError):
        editor.apply_edits(target, edits)
    assert target.read_text() == "old\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["note.md"]


def test_batch_cli_dry_run_and_mode(tmp_path):
    target = tmp_path / "note.md"
    target.write_text("old\n")
    target.chmod(0o640)
    edits = tmp_path / "edits.json"
    edits.write_text(
        json.dumps([{"op": "replace", "anchor": "old", "replacement": "new"}])
    )
    assert (
        editor.main(
            ["apply", "--file", str(target), "--edits", str(edits), "--dry-run"]
        )
        == 0
    )
    assert target.read_text() == "old\n"
    assert editor.main(["apply", "--file", str(target), "--edits", str(edits)]) == 0
    assert target.read_text() == "new\n" and target.stat().st_mode & 0o777 == 0o640


def test_batch_detects_changed_input_before_replace(tmp_path, monkeypatch):
    target = tmp_path / "note.md"
    target.write_text("old\n")
    monkeypatch.setattr(
        editor, "_coherence_gate", lambda *a: target.write_text("foreign\n")
    )
    with pytest.raises(editor.ContextEditError, match="changed during"):
        editor.apply_edits(
            target, [{"op": "replace", "anchor": "old", "replacement": "new"}]
        )
    assert target.read_text() == "foreign\n"


def test_file_operand_symlink_and_malformed_json_refused(tmp_path):
    target = tmp_path / "note.md"
    target.write_text("old\n")
    link = tmp_path / "link"
    link.symlink_to(target)
    assert (
        editor.main(
            [
                "replace",
                "--file",
                str(target),
                "--anchor-file",
                str(link),
                "--replacement",
                "x",
            ]
        )
        == 1
    )
    bad = tmp_path / "bad"
    bad.write_text("{")
    assert editor.main(["apply", "--file", str(target), "--edits", str(bad)]) == 1
    assert target.read_text() == "old\n"


def test_batch_atomic_replace_failure_preserves_old_bytes_and_no_temp(
    tmp_path, monkeypatch
):
    target = tmp_path / "note.md"
    target.write_text("old\n")

    def fail(*args):
        raise OSError("synthetic pre-rename failure")

    monkeypatch.setattr(editor.os, "replace", fail)
    with pytest.raises(OSError, match="synthetic"):
        editor.apply_edits(
            target, [{"op": "replace", "anchor": "old", "replacement": "new"}]
        )
    assert target.read_text() == "old\n"
    assert list(tmp_path.iterdir()) == [target]


def test_batch_final_gates_run_once_and_final_refusal_preserves_bytes(
    tmp_path, monkeypatch
):
    target = tmp_path / "note.md"
    target.write_text("old\n")
    calls = []
    gate = editor._coherence_gate
    monkeypatch.setattr(
        editor, "_coherence_gate", lambda *a: (calls.append(a), gate(*a))[1]
    )
    editor.apply_edits(
        target,
        [
            {"op": "replace", "anchor": "old", "replacement": "intermediate"},
            {"op": "replace", "anchor": "intermediate", "replacement": "new"},
        ],
        dry_run=True,
    )
    assert len(calls) == 1 and target.read_text() == "old\n"
    with pytest.raises(editor.ContextEditError, match="line budget"):
        editor.apply_edits(
            target,
            [{"op": "replace", "anchor": "old", "replacement": "one\ntwo"}],
            max_lines=1,
        )
    assert target.read_text() == "old\n"


def test_batch_cli_duplicate_keys_refused(tmp_path):
    target = tmp_path / "note.md"
    target.write_text("old\n")
    edits = tmp_path / "edits.json"
    edits.write_text(
        '[{"op":"replace","anchor":"old","anchor":"different","replacement":"new"}]'
    )
    assert editor.main(["apply", "--file", str(target), "--edits", str(edits)]) == 1
    assert target.read_text() == "old\n"


def test_multiple_stdin_operands_are_not_silently_consumed(tmp_path):
    target = tmp_path / "note.md"
    target.write_text("old\n")
    with pytest.raises(SystemExit) as failure:
        editor.main(
            ["replace", "--file", str(target), "--anchor", "-", "--replacement", "-"]
        )
    assert failure.value.code == 2 and target.read_text() == "old\n"




def test_atomic_writer_persists_mode_and_renamed_parent(tmp_path, monkeypatch):
    import os
    import stat

    path = tmp_path / "record.md"
    path.write_text("before")
    path.chmod(0o640)
    real = edit.os.fsync
    calls = []

    def tracked(fd):
        status = os.fstat(fd)
        calls.append((stat.S_ISDIR(status.st_mode), stat.S_IMODE(status.st_mode)))
        return real(fd)

    monkeypatch.setattr(edit.os, "fsync", tracked)
    edit._atomic_write(path, "after")
    assert calls == [(False, 0o640), (True, stat.S_IMODE(tmp_path.stat().st_mode))]
    assert path.read_text() == "after"
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


@pytest.mark.parametrize("phase", ["file-sync", "rename", "directory-sync"])
def test_batch_failures_name_the_real_commit_boundary(tmp_path, monkeypatch, phase):
    import os
    import stat

    path = tmp_path / "record.md"
    path.write_text("original\n")
    real_sync = edit.os.fsync
    real_replace = edit.os.replace

    def sync(fd):
        directory = stat.S_ISDIR(os.fstat(fd).st_mode)
        if (phase == "file-sync" and not directory) or (
            phase == "directory-sync" and directory
        ):
            raise OSError("synthetic " + phase)
        return real_sync(fd)

    def replace(*args):
        if phase == "rename":
            raise OSError("synthetic rename")
        return real_replace(*args)

    with monkeypatch.context() as m:
        m.setattr(edit.os, "fsync", sync)
        m.setattr(edit.os, "replace", replace)
        with pytest.raises(OSError, match="synthetic"):
            edit.apply_edits(
                path,
                [{"op": "replace", "anchor": "original", "replacement": "committed"}],
            )
    expected = "committed\n" if phase == "directory-sync" else "original\n"
    assert path.read_text() == expected
    assert sorted(p.name for p in tmp_path.iterdir()) == ["record.md"]
    if phase == "directory-sync":
        with pytest.raises(edit.ContextEditError):
            edit.apply_edits(
                path,
                [{"op": "replace", "anchor": "original", "replacement": "committed"}],
            )
        assert path.read_text() == "committed\n"
    else:
        edit.apply_edits(
            path, [{"op": "replace", "anchor": "original", "replacement": "committed"}]
        )
        assert path.read_text() == "committed\n"


@pytest.mark.parametrize("phase", ["before-rename", "after-rename"])
def test_process_loss_keeps_complete_target_and_recovery_reads_truth(tmp_path, phase):
    import subprocess
    import sys

    path = tmp_path / "record.md"
    path.write_text("old\n")
    marker = tmp_path / "boundary"
    script = tmp_path / "interrupt.py"
    # os._exit models abrupt process loss with no exception unwinding. It
    # leaves pre-rename staging custody intact, never a partial target.
    script.write_text(
        "import os,sys\nfrom pathlib import Path\n"
        + "sys.path.insert(0, "
        + repr(str(Path(__file__).resolve().parent))
        + ")\n"
        + "import context_edit as e\nreal=e.os.replace\n"
        + "def abrupt(src,dst):\n"
        + "    Path("
        + repr(str(marker))
        + ').write_text("reached")\n'
        + ("    real(src,dst)\n" if phase == "after-rename" else "")
        + "    os._exit(73)\n"
        + "e.os.replace=abrupt\n"
        + "e.apply_edits(Path("
        + repr(str(path))
        + '),[{"op":"replace","anchor":"old","replacement":"new"}])\n'
    )
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, timeout=5
    )
    assert result.returncode == 73 and marker.read_text() == "reached"
    assert path.read_bytes() == (b"old\n" if phase == "before-rename" else b"new\n")
    if phase == "before-rename":
        staged = [
            p
            for p in tmp_path.iterdir()
            if p.name not in {"record.md", "boundary", "interrupt.py"}
        ]
        assert len(staged) == 1 and staged[0].read_bytes() == b"new\n"
        edit.apply_edits(
            path, [{"op": "replace", "anchor": "old", "replacement": "new"}]
        )
        assert staged[0].read_bytes() == b"new\n"  # retained evidence, not discarded
    else:
        with pytest.raises(edit.ContextEditError):
            edit.apply_edits(
                path, [{"op": "replace", "anchor": "old", "replacement": "new"}]
            )
    assert path.read_bytes() == b"new\n"
