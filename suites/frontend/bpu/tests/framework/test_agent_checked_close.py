"""A swallowed error is still a passing body and must get strict finish."""
from types import SimpleNamespace
import pytest
from suites.frontend.bpu.runtime.fixtures import close_agent
from suites.frontend.bpu.mbtb.agent.main import MbtbAgent
import asyncio

pytestmark=pytest.mark.selftest


@pytest.mark.parametrize('reports,expected',(({},True),({'setup':'passed','call':'passed'},True),
    ({'setup':'failed'},False),({'call':'failed'},False),({'setup':'skipped'},False),({'call':'skipped'},False)))
async def test_actual_body_reports_control_only_normal_finish_not_cleanup(reports,expected):
    calls=[]
    async def close(**kwargs):calls.append(kwargs)
    await close_agent(SimpleNamespace(aclose=close),SimpleNamespace(node=SimpleNamespace(_bpu_body_reports=reports)),checked=True)
    assert calls==[dict(check=expected)]


@pytest.mark.parametrize('checked',(False,True))
async def test_independent_cleanup_error_is_never_suppressed(checked):
    error=OSError('independent resource-close failure')
    async def close(**kwargs):raise error
    with pytest.raises(OSError) as caught:
        await close_agent(SimpleNamespace(aclose=close),SimpleNamespace(node=SimpleNamespace(
            _bpu_body_reports={'call':'failed'})),checked=checked)
    assert caught.value is error


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
