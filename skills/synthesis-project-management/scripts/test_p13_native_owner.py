import inspect
import native_identity
import project_state
import run_admission
import team_contract as tc
from test_team_contract import contract


def test_native_error_is_the_same_owner():
    assert project_state.ProjectStateError is native_identity.ProjectStateError
    assert "resolve_native_row" in inspect.getsource(project_state.row_for_event)
    assert "coordination.passive_board_snapshot" in inspect.getsource(run_admission._snapshot)


def test_historical_role_time_is_explicit():
    d = contract()
    d["governance"]["role_history"] = [{"id":"a-one","person":"p-one","role":"maintainer","scope":["repo-one"],"backup":"p-two","opened":"2020-01-01T00:00:00Z","closed":"2020-01-02T00:00:00Z","accepted_work":["work-one"],"inventory_sha256":"a"*64,"appointed_by":"p-two","approval_digest":"b"*64,"native_ref":"cc:synthetic"}]
    assert "maintainer" in tc.effective_roles(d,"p-one",scope="repo-one",observed_at="2020-01-01T12:00:00Z")
    assert "maintainer" not in tc.effective_roles(d,"p-one",scope="repo-one",observed_at="2020-01-02T00:00:00Z")
