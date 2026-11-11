"""Gap-driven all120 RAW_CAPACITY owners, original public grant/slot ledgers."""

from dataclasses import replace

import pytest

from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.replay.transactions import Cause


@pytest.mark.parametrize("start",(0,255))
@pytest.mark.parametrize("lane",range(3))
@pytest.mark.parametrize("wake",("pool_credit","address_prefix"))
async def test_full120_RAW_capacity_exclusive128_preserves_every_original_public_grant_and_slot(sq_replay,start,lane,wake):
    replay=sq_replay
    end=start+128
    reqs=[replay.request(Cause.RAW_CAPACITY,rob=10+i,lq=i,sq=end,tag=64+i) for i in range(120)]
    for req in reqs:
        await replay.cycle({lane:req},raw_full=True,address_ready=SqPtr.encode(start),dequeue=SqPtr.encode(start),upper=SqPtr.encode(start+64))
        assert not any(item.valid for item in replay.response.replay)
    assert replay.response.lq_full and replay.response.replay_allocate
    for _ in range(6):
        await replay.cycle()
        assert not any(item.valid for item in replay.response.replay)
    await replay.cycle(**(dict(raw_full=False) if wake=="pool_credit" else dict(address_ready=SqPtr.encode(end))))
    grants={}
    for _ in range(360):
        pre=replay.response
        await replay.cycle(ready=(True,True,True))
        for bank in range(3):
            response=pre.replay[bank]
            if not response.valid:continue
            lq=120*int(response.lq_idx_flag)+response.lq_idx_value
            assert lq in range(120) and lq not in grants
            slot=response.replay_queue_idx
            assert slot%3==bank and slot not in grants.values()
            req=reqs[lq]
            assert (response.rob_idx_flag,response.rob_idx_value,response.rob_idx_former)==(
                int(req.uop.rob.flag),req.uop.rob.value,int(req.uop.rob.former))
            assert (response.sq.first,response.sq.second,response.sq.value)==(
                int(req.uop.sq.first),int(req.uop.sq.second),req.uop.sq.value)
            assert response.checkpoint_id==req.uop.checkpoint
            grants[lq]=slot
        if len(grants)==120:break
    assert len(grants)==120 and set(grants.values())==set(range(120))
    for lq,slot in sorted(grants.items()):
        feedback=replace(reqs[lq],replay_feedback=True,slot=slot,need_replay=False,causes=0)
        await replay.cycle({lane:feedback},ready=(False,False,False))
    await replay.idle(12)
    assert not replay.response.lq_full and not replay.response.replay_allocate
    assert not any(item.valid for item in replay.response.replay)
