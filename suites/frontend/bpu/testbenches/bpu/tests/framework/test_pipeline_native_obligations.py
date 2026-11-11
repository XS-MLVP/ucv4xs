"""Production autonomous observer controls on real native BPU, not DUT credit."""
import asyncio
from contextlib import suppress
from copy import deepcopy

import pytest

from suites.frontend.bpu.testbenches.bpu.tests.scenarios.pipeline import check_stream
from suites.frontend.bpu.testbenches.bpu.checker.pipeline import PipelineChecker
from suites.frontend.bpu.testbenches.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.testbenches.bpu.env.agent.pipeline import PipelineObservation
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuRedirect

pytestmark = pytest.mark.selftest
PC = 0x40000800


async def test_corrupted_internal_target_in_the_real_stream_case_latches_before_model_advancement(bpu_agent,monkeypatch):
    capture=PipelineChecker.capture
    injected=[]

    def corrupt(checker,row,event):
        if (not injected and not row['inputs']['reset'] and row['observed']['valids'][0]):
            before=deepcopy(checker.model.state())
            damaged=deepcopy(row)
            damaged['observed']['choices'][0]['target']^=2
            capture(checker,damaged,event)
            injected.append((checker,before))
        else:
            capture(checker,row,event)

    monkeypatch.setattr(PipelineChecker,'capture',corrupt)
    with pytest.raises(AssertionError) as first:
        await check_stream(bpu_agent)
    assert len(injected)==1
    checker,before=injected[0]
    assert checker.failure is first.value and checker.model.state()==before
    with pytest.raises(AssertionError) as last:
        checker.finish()
    assert last.value is first.value


async def test_closed_autonomous_monitor_cannot_turn_a_real_accepted_redirect_into_clean_finish(bpu_agent):
    phr=BpuPhrChecker(scope='autonomous-monitor-stopped',record_limit=8)
    with pytest.raises(AssertionError,match='planned owned redirect'):
        async with PipelineObservation(bpu_agent) as observation,bpu_agent.observe_phr(phr) as history:
            await bpu_agent.reset(PC)
            source=await bpu_agent.next_transaction(start_pc=PC)
            await bpu_agent.set_ready(prediction=False,meta=True)
            await history.drain()
            request=BpuRedirect(PC+0x400,source.meta.redirect)
            observation.checker.plan_redirect(source,request)
            subscription=observation.subscription
            bpu_agent._execution.reactor.cancel_subscription(subscription)
            with suppress(asyncio.CancelledError):
                await subscription.task
            # PHR still proves the actual input occurred. The autonomous
            # checker must keep its unpaid planned-input obligation.
            await bpu_agent.redirect(request)
            await history.drain()


async def test_equal_metadata_cannot_supply_an_unplanned_input_owner(bpu_agent):
    phr=BpuPhrChecker(scope='unplanned-autonomous-input',record_limit=8)
    with pytest.raises(AssertionError,match='planned redirect'):
        async with PipelineObservation(bpu_agent) as observation,bpu_agent.observe_phr(phr) as history:
            await bpu_agent.reset(PC)
            source=await bpu_agent.next_transaction(start_pc=PC)
            await bpu_agent.set_ready(prediction=False,meta=True)
            await history.drain()
            await bpu_agent.redirect(BpuRedirect(PC+0x400,source.meta.redirect))
            observation.checker.raise_failure()
