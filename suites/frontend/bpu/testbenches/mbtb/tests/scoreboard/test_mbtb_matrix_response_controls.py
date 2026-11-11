"""Same legal native program with a corrupt RESPONSE, not an illegal stimulus.

Injection is after the native SDK/monitor comparison, at the independent
property check's observation boundary. It does not mutate RTL or its state.
"""
from dataclasses import replace
import pytest
import suites.frontend.bpu.testbenches.mbtb.tests.scenarios.learning_matrix as scenarios
from suites.frontend.bpu.testbenches.mbtb.checker.learning_matrix import check_payload
from suites.frontend.bpu.testbenches.mbtb.model.learning_matrix import PAYLOAD_CASES
from suites.frontend.bpu.testbenches.mbtb.tests.framework.test_mbtb_runtime_obligations import running

pytestmark = [pytest.mark.selftest, pytest.mark.dut('mbtb')]


@pytest.mark.parametrize('fault', ('target', 'type', 'direction', 'neighbor'))
async def test_legal_native_feedback_cannot_hide_a_corrupt_final_response(dut_factory, monkeypatch, fault):
    case = next(c for c in PAYLOAD_CASES if c.mode == 'conditional-nt')
    seen = []
    def damaged(case, actual, peer):
        # First assert the undamaged response passes the identical property.
        check_payload(case, actual, peer)
        selected = next(s for s,e in enumerate(actual.entries) if e.valid and e.position == (8 if fault == 'neighbor' else case.position))
        entries = list(actual.entries)
        entry = entries[selected]
        fields = ({'target': entry.target ^ 2} if fault in ('target', 'neighbor') else
                  {'branch_type': 3} if fault == 'type' else {'taken': entry.taken ^ 1})
        entries[selected] = replace(entry, **fields)
        seen.append(fault)
        check_payload(case, replace(actual, entries=tuple(entries)), peer)
    monkeypatch.setattr(scenarios, 'check_payload', damaged)
    async with running(dut_factory) as agent:
        with pytest.raises(AssertionError, match='payload/type/target/direction'):
            await scenarios.check_payload_matrix(agent, case)
        assert seen == [fault]
