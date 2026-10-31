"""Real DUT ownership handoff must restore ordinary transaction monitoring."""

import pytest

from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.case.definitions import PC


@pytest.mark.parametrize('body_failure', (False, True))
async def test_coherent_phr_scope_restores_normal_transactions(bpu_agent, body_failure):
    checker = BpuPhrChecker(scope=dict(body_failure=body_failure))
    sentinel = AssertionError('deliberate scope body failure')
    try:
        async with bpu_agent.observe_phr(checker):
            await bpu_agent.reset(PC)
            coherent = await bpu_agent.next_transaction(start_pc=PC)
            assert coherent.meta.perf.start_pc == PC
            if body_failure:
                raise sentinel
    except AssertionError as error:
        assert body_failure and error is sentinel
    else:
        assert not body_failure
    # A new epoch exercises the newly created ordinary monitors rather than
    # reading buffered observations from the previous coherent scope.
    await bpu_agent.reset(PC)
    ordinary = await bpu_agent.next_transaction(start_pc=PC)
    assert ordinary.meta.perf.start_pc == ordinary.prediction.start_pc == PC
    assert ordinary.prediction.taken == coherent.prediction.taken == 0
    assert ordinary.meta_tick > coherent.meta_tick
    assert checker.summary()['checks']['failed'] == 0
