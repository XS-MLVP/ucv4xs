"""Primary compare errors and their original state survive later activity."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace as N
import pytest
from toffee import ScoreboardMismatch
from bpuverify.bpu.checker.main_original_order import Checks
from bpuverify.bpu.model.main_original_order import Program
from bpuverify.bpu.env.main_original_lifetime import close_pressure


def checker():
    environment=N(checker=N(current_event=None,raise_failure=lambda:None))
    return Checks(environment,Program('old-then-young','retained-under-reads',0))


def row(p,*,wrong=False):
    entry=p.services[-1]
    return dict(training=dict(valid=0,ready=1),read=dict(valid=1,row=0),
        writes=[dict(valid=1,ready=0,bits=entry),dict(valid=0,ready=0,bits={}),
                dict(valid=1,ready=0,bits=dict(row=0,mask=2 if wrong else 1,counters=(0,2) if wrong else (2,0)))],
        incoming=[],direction=dict(valid=0,ready=1,bits={}),dirty=[[1,0],[0,0]],
        queue=dict(enqueue=0,dequeue=0,full=1))


def test_direct_failure_is_sticky_and_its_first_input_state_is_immutable():
    c=checker();actual={'mask':2};expected={'mask':1}
    with pytest.raises(ScoreboardMismatch) as first:c.check(expected,actual,'direction owner')
    snapshot=deepcopy(c.summary()['first_error']);actual['mask']=0
    with pytest.raises(ScoreboardMismatch) as later:c.check(5,6,'must not replace original')
    assert later.value is first.value is c.failure
    assert c.board.status.checked==c.board.status.failed==1
    assert c.summary()['first_error']==snapshot and snapshot['actual']=={'mask':2}
    json.dumps(c.summary())


async def test_passive_failure_is_published_once_before_control_wait_can_timeout():
    c=checker();c.close_when_retained=asyncio.get_running_loop().create_future()
    c.incoming=[dict(tick=5,owner=0,bits=c.program.effect(i)) for i in (0,1)]
    c.directions=[dict(tick=5,bits={}),dict(tick=7,bits={})]
    sampled=row(c.program,wrong=True)
    with pytest.raises(ScoreboardMismatch) as first:c.capture_state(N(tick=10),sampled)
    before=c.board.status.checked;state=deepcopy(c.summary()['first_error'])
    sampled['writes'][2]['bits']['mask']=0
    c.capture_state(N(tick=11),sampled)
    assert c.failure is first.value and c.board.status.checked==before and c.board.status.failed==1
    assert c.summary()['first_error']==state and state['retention']['writes'][2]['bits']['mask']==2
    assert not c.close_when_retained.done()
    with pytest.raises(ScoreboardMismatch) as raised:c.raise_failure()
    assert raised.value is first.value
    c.close_when_retained.cancel()


async def test_a_correct_passive_retained_boundary_returns_the_identical_actual_event():
    c=checker();c.close_when_retained=asyncio.get_running_loop().create_future()
    c.incoming=[dict(tick=5,owner=0,bits=c.program.effect(i)) for i in (0,1)]
    c.directions=[dict(tick=5,bits={}),dict(tick=7,bits={})]
    event=N(tick=10);c.capture_state(event,row(c.program))
    assert c.close_when_retained.result() is event and c.failure is None
    assert c.retained_witness['tick']==10 and 'first_error' not in c.summary()


async def test_later_native_service_can_be_recorded_without_rechecking_or_replacing_first_error():
    c=checker()
    with pytest.raises(ScoreboardMismatch) as first:c.check(1,2,'first')
    c.write_accepted(2,N(accepted_tick=12,value={'mask':2}))
    assert c.written[2]==[dict(tick=12,bits={'mask':2})]
    assert c.board.status.checked==1 and c.failure is first.value


async def test_pending_pressure_cancellation_completes_owned_work_without_new_failure():
    future=asyncio.get_running_loop().create_future()
    await close_pressure(future)
    assert future.cancelled()


async def test_cleanup_error_never_masks_an_existing_semantic_mismatch():
    future=asyncio.get_running_loop().create_future();cleanup=ValueError('cleanup');future.set_exception(cleanup)
    primary=AssertionError('semantic')
    await close_pressure(future,primary)
    assert primary.__notes__==["pressure cleanup: ValueError('cleanup')"]


async def test_cleanup_failure_without_a_primary_still_fails():
    future=asyncio.get_running_loop().create_future();error=ValueError('cleanup');future.set_exception(error)
    with pytest.raises(ValueError) as raised:await close_pressure(future)
    assert raised.value is error


async def test_the_same_primary_is_consumed_without_redundant_notes():
    future=asyncio.get_running_loop().create_future();primary=AssertionError('semantic');future.set_exception(primary)
    await close_pressure(future,primary)
    assert not hasattr(primary,'__notes__')
