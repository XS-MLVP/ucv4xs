"""RAW_CAPACITY waits on the original exclusive SQ boundary, not SQ emptiness."""
from dataclasses import replace

import pytest

from lsqverify.raw.types import SqPtr
from lsqverify.replay.types import Cause


@pytest.mark.parametrize("start",(0,63,255))
@pytest.mark.parametrize("distance",(127,128))
@pytest.mark.parametrize("lane",range(3))
@pytest.mark.parametrize("wake",("pool_credit","address_prefix"))
async def test_RAW_capacity_original_slot_waits_full_boundary_and_accepts_either_real_source(replay,start,distance,lane,wake):
    env=replay
    end=start+distance
    req=env.request(Cause.RAW_CAPACITY,rob=20,lq=10,sq=end,tag=85)
    await env.cycle({lane:req},raw_full=True,address_ready=SqPtr.encode(start),dequeue=SqPtr.encode(start),upper=SqPtr.encode(start+64))
    for _ in range(8):
        await env.cycle()
        assert not any(env.observed[f"io_replay_{b}_valid"] for b in range(3))
    await env.cycle(address_ready=SqPtr.encode(end-1))
    for _ in range(4):
        await env.cycle()
        assert not any(env.observed[f"io_replay_{b}_valid"] for b in range(3))
    await env.cycle(**dict(raw_full=False) if wake=="pool_credit" else dict(address_ready=SqPtr.encode(end)))
    for _ in range(20):
        if any(env.observed[f"io_replay_{b}_valid"] for b in range(3)):break
        await env.cycle()
    bank=next(b for b in range(3) if env.observed[f"io_replay_{b}_valid"])
    p=f"io_replay_{bank}_bits_"
    slot=env.observed[p+"replayQueueIdx"]
    assert env.observed[p+"uop_sqIdx_first_flag"]==int(req.uop.sq.first)
    assert env.observed[p+"uop_sqIdx_second_flag"]==int(req.uop.sq.second) and env.observed[p+"uop_sqIdx_value"]==req.uop.sq.value
    await env.cycle(raw_full=True)
    assert env.observed[f"io_replay_{bank}_valid"] and env.observed[p+"replayQueueIdx"]==slot
    await env.cycle(ready=tuple(b==bank for b in range(3)))
    feedback=replace(req,replay_feedback=True,slot=slot,need_replay=False,causes=0)
    await env.cycle({lane:feedback},ready=(False,False,False))
    await env.idle(8)
    assert not env.observed["io_replayAllocate"] and not any(env.observed[f"io_replay_{b}_valid"] for b in range(3))
