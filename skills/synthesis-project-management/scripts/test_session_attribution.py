from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(ROOT / "skills/synthesis-context-lifecycle/scripts"),
    str(ROOT / "skills/synthesis-project-management/scripts"),
]
import context_doctor as doctor  # noqa: E402 - source-bound import follows path/bootstrap initialization
from test_team_contract import _team_board  # noqa: E402 - source-bound import follows path/bootstrap initialization


def test_same_day_distinct_native_sessions_count_independently(tmp_path):
    p = tmp_path / "2026-09.md"
    p.write_text(
        '## 2026-09-26 First\nSession identity: {"session":"session-a","person":"p-one","native":"codex:a"}\n## 2026-09-26 Second\nSession identity: {"session":"session-b","person":"p-two","native":"cc:b"}\n'
    )
    assert doctor.session_entry_count(tmp_path) == 2


def test_identified_session_subheadings_do_not_multiply_it(tmp_path):
    p = tmp_path / "2026-09.md"
    p.write_text(
        '## 2026-09-26 First\nSession identity: {"session":"session-a","person":"p-one","native":"codex:a"}\n### 2026-09-26 Subsection\n'
    )
    assert doctor.session_entry_count(tmp_path) == 1


def test_same_session_cannot_be_relabelled_by_ordinary_mutation(tmp_path):
    c, board, row, before = _team_board(tmp_path)
    row.person = "p-two"
    after = c.replace_table(before, [row])
    with pytest.raises(ValueError):
        c.validate_team_transition(board, before, after)
