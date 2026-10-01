import pytest
import team_contract as tc
from test_team_contract import contract

def record(opened, closed=None):
    return {'id':'a-one','person':'p-one','role':'maintainer','scope':['repo-one'],
            'backup':'p-two','opened':opened,'closed':closed,'accepted_work':['work-one'],
            'inventory_sha256':'a'*64,'appointed_by':'p-two','approval_digest':'b'*64,
            'native_ref':'cc:synthetic'}

@pytest.mark.parametrize('opened,closed,expected', [
    ('2020-01-01T00:00:00Z', None, True),
    ('2020-01-01T00:00:00Z', '2020-01-02T00:00:00Z', False),
    ('2099-01-01T00:00:00Z', None, False),
])
def test_scoped_role_obeys_appointment_interval(opened, closed, expected):
    declaration=contract()
    declaration['governance']['role_history']=[record(opened, closed)]
    assert ('maintainer' in tc.effective_roles(declaration, 'p-one', scope='repo-one')) == expected
