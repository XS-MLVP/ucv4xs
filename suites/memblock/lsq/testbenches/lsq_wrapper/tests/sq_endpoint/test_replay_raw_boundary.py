"""RAW_CAPACITY waits on the original exclusive SQ boundary, not SQ emptiness."""

from dataclasses import replace

import pytest

from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.replay.transactions import Cause


@pytest.mark.parametrize("start",(0,63,255))
@pytest.mark.parametrize("distance",(127,128))
@pytest.mark.parametrize("lane",range(3))
@pytest.mark.parametrize("wake",("pool_credit","address_prefix"))
async def test_RAW_capacity_original_slot_waits_full_boundary_and_accepts_either_real_source(sq_replay,start,distance,lane,wake):
    env=sq_replay
    end=start+distance
    req=env.request(Cause.RAW_CAPACITY,rob=20,lq=10,sq=end,tag=85)
    await env.cycle({lane:req},raw_full=True,address_ready=SqPtr.encode(start),dequeue=SqPtr.encode(start),upper=SqPtr.encode(start+64))
    for _ in range(8):
        await env.cycle()
        assert not any(item.valid for item in env.response.replay)
    await env.cycle(address_ready=SqPtr.encode(end-1))
    for _ in range(4):
        await env.cycle()
        assert not any(item.valid for item in env.response.replay)
    await env.cycle(**dict(raw_full=False) if wake=="pool_credit" else dict(address_ready=SqPtr.encode(end)))
    for _ in range(20):
        if any(item.valid for item in env.response.replay):break
        await env.cycle()
    bank=next(b for b,item in enumerate(env.response.replay) if item.valid)
    response=env.response.replay[bank]
    slot=response.replay_queue_idx
    assert response.sq.first==int(req.uop.sq.first)
    assert response.sq.second==int(req.uop.sq.second) and response.sq.value==req.uop.sq.value
    await env.cycle(raw_full=True)
    assert env.response.replay[bank].valid and env.response.replay[bank].replay_queue_idx==slot
    await env.cycle(ready=tuple(b==bank for b in range(3)))
    feedback=replace(req,replay_feedback=True,slot=slot,need_replay=False,causes=0)
    await env.cycle({lane:feedback},ready=(False,False,False))
    await env.idle(8)
    assert not env.response.replay_allocate and not any(item.valid for item in env.response.replay)
