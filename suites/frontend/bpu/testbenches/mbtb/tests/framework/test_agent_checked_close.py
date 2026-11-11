"""A swallowed error is still a passing body and must get strict finish."""
from types import SimpleNamespace
import asyncio

import pytest

from suites.frontend.bpu.testbenches.mbtb.env.agent.main import MbtbAgent

pytestmark=pytest.mark.selftest


@pytest.mark.parametrize('bad',(0,1,2,None,'enabled'))
async def test_mainbtb_enable_rejects_encoded_or_implicit_coercion_before_driving(bad):
    agent=object.__new__(MbtbAgent);agent._started=True;agent._finished=False
    # No control driver is installed: a bad level must fail before accessing it.
    with pytest.raises(ValueError,match='semantic bool'):await agent.set_enabled(bad)


@pytest.mark.parametrize('bad',(0,-1,True,1.5,None))
async def test_mainbtb_reset_rejects_a_non_event_before_asserting_reset(bad):
    agent=object.__new__(MbtbAgent);agent._started=True;agent._finished=False
    with pytest.raises(ValueError,match='positive integer'):await agent.reset(bad)


@pytest.mark.parametrize('same_observed_failure',(True,False))
async def test_lookup_tail_cleanup_does_not_repeat_a_known_error_or_hide_an_independent_one(same_observed_failure):
    known=AssertionError('observed wire mismatch')
    independent=RuntimeError('independent stage cleanup')
    agent=object.__new__(MbtbAgent)
    agent.reference=SimpleNamespace(failure=known,failure_observed=True)
    async def failed():raise known if same_observed_failure else independent
    task=asyncio.create_task(failed())
    await asyncio.sleep(0)
    agent._lookup_tails={task}
    if same_observed_failure:
        await agent._close_lookup_tails()
    else:
        with pytest.raises(RuntimeError) as caught:await agent._close_lookup_tails()
        assert caught.value is independent
    assert agent._lookup_tails==set()
