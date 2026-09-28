from copy import deepcopy
import pytest
from native_codex_turn import transcript
from test_managed_productive import work_stream
from test_native_callback import SID


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "in-progress-end",
        "unseen-terminal",
        "duplicate-terminal-item",
        "changed-terminal-item",
    ],
)
def test_native_item_terminal_semantics_are_consistent(fault):
    rows = work_stream()
    item = deepcopy(rows[3]["params"]["item"])
    if fault == "in-progress-end":
        rows[3]["params"]["item"]["status"] = "inProgress"
    if fault in (None, "duplicate-terminal-item", "changed-terminal-item"):
        rows[-1]["params"]["turn"]["items"] = [deepcopy(item)]
    if fault == "unseen-terminal":
        item["id"] = "unseen"
        rows[-1]["params"]["turn"]["items"] = [item]
    if fault == "duplicate-terminal-item":
        rows[-1]["params"]["turn"]["items"].append(deepcopy(item))
    if fault == "changed-terminal-item":
        rows[-1]["params"]["turn"]["items"][0]["command"] = "different command"
    if fault:
        with pytest.raises(ValueError):
            transcript(rows, SID, "current-turn")
    else:
        assert transcript(rows, SID, "current-turn")["status"] == "completed"
