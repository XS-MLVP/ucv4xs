"""A restored invalid prefix may become a valid direct-path consumer later."""
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.bpu.checker.common_query import CommonQueryChecks
from suites.frontend.bpu.bpu.checker.superseding_recovery import SupersedingRecoveryChecks
from suites.frontend.bpu.bpu.model.common_history import Value
from suites.frontend.bpu.bpu.model.superseding_recovery import SupersedingRecoveryProgram, PROFILES


@pytest.mark.parametrize('profile', PROFILES)
def test_registered_endpoint_snapshot_does_not_freeze_the_later_public_validity(monkeypatch, profile):
    # Keep this local test on the added endpoint policy; the parent observers
    # independently compare the full state throughout real DUT execution.
    monkeypatch.setattr(CommonQueryChecks, 'capture_state', lambda *_: None)
    p = SupersedingRecoveryProgram(profile)
    c = object.__new__(SupersedingRecoveryChecks)
    c.program, c.failure, c.intermediate_state, c.final_state = p, None, None, None
    c.selected = (dict(iteration=NS(count=16)), {})
    c.recoveries = [dict(tick=10), dict(tick=12)]
    c.query, c.model = NS(value=p.restored), NS(cursor=p.iteration(16))
    def check(expected, actual, _):
        assert expected == actual
    c.check_query = check
    row = dict(iteration=dict(redirect=dict(valid=0), state=p.iteration(16)), state=p.restored.mapping())
    c.capture_state(NS(tick=16), row)
    assert c.failure is None and c.final_state == dict(tick=16, actual=row['state'], iteration=p.iteration(16))
    c.query.value = Value(True, p.restored.ghr, p.restored.bw)
    c.model.cursor = 0
    row = dict(iteration=dict(redirect=dict(valid=0), state=0), state=c.query.value.mapping())
    c.capture_state(NS(tick=18), row)
    assert c.failure is None and c.final_state['tick'] == 16
