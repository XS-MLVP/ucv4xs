"""Checker failures belong to pytest's awaiting task, not pump teardown."""
import pytest
from toffee import ClockCycles,Execution,MemoryBackend

from suites.frontend.bpu.runtime.wait import wait_condition


@pytest.mark.parametrize('point',('sample','satisfied'))
@pytest.mark.parametrize('error_type',(AssertionError,ValueError,RuntimeError))
async def test_callback_error_preserves_first_exception_and_does_not_poison_execution(point,error_type):
    clock,calls = object(),[]
    error = error_type('original checker failure')
    def sample():
        calls.append('sample')
        if point=='sample':raise error
        return dict(ready=1)
    def satisfied(state):
        calls.append('satisfied')
        raise error
    async with Execution(MemoryBackend(clock)):
        with pytest.raises(error_type) as caught:
            await wait_condition(clock,sample=sample,satisfied=satisfied,name='failing-checker',timeout_cycles=8)
        assert caught.value is error
        expected = ['sample'] if point=='sample' else ['sample','satisfied']
        assert calls==expected
        await ClockCycles(clock,3)
        assert calls==expected  # Both losing triggers were cancelled normally.
        result = await wait_condition(clock,sample=lambda:42,satisfied=lambda state:state==42,
            name='pump-remains-usable',timeout_cycles=8)
        assert result.state==42 and result.samples>=1


async def test_timeout_still_contains_state_tick_and_budget():
    clock = object()
    async with Execution(MemoryBackend(clock)):
        with pytest.raises(TimeoutError,match=r'pending-owner.*2 cycles.*tick=.*last_state=.*pending'):
            await wait_condition(clock,sample=lambda:dict(pending=1),satisfied=lambda _:False,
                name='pending-owner',timeout_cycles=2)
