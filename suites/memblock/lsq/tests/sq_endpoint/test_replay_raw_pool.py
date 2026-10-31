"""Gap-driven all120 RAW_CAPACITY owners, original public grant/slot ledgers."""

from dataclasses import replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.replay.types import Cause


@pytest.mark.parametrize("start",(0,255))
@pytest.mark.parametrize("lane",range(3))
@pytest.mark.parametrize("wake",("pool_credit","address_prefix"))
async def test_full120_RAW_capacity_exclusive128_preserves_every_original_public_grant_and_slot(replay,start,lane,wake):
    end=start+128
    reqs=[replay.request(Cause.RAW_CAPACITY,rob=10+i,lq=i,sq=end,tag=64+i) for i in range(120)]
    for req in reqs:
        await replay.cycle({lane:req},raw_full=True,address_ready=SqPtr.encode(start),dequeue=SqPtr.encode(start),upper=SqPtr.encode(start+64))
        assert not any(replay.observed[P.io(f"replay_{b}_valid")] for b in range(3))
    assert replay.observed[P.p_lqFull] and replay.observed[P.p_replayAllocate]
    for _ in range(6):
        await replay.cycle()
        assert not any(replay.observed[P.io(f"replay_{b}_valid")] for b in range(3))
    await replay.cycle(**(dict(raw_full=False) if wake=="pool_credit" else dict(address_ready=SqPtr.encode(end))))
    grants={}
    for _ in range(360):
        pre=dict(replay.observed)
        await replay.cycle(ready=(True,True,True))
        for bank in range(3):
            p=P.io(f"replay_{bank}_")
            if not pre[p+"valid"]:continue
            lq=120*pre[p+"bits_uop_lqIdx_flag"]+pre[p+"bits_uop_lqIdx_value"]
            assert lq in range(120) and lq not in grants
            slot=pre[p+"bits_replayQueueIdx"]
            assert slot%3==bank and slot not in grants.values()
            req=reqs[lq]
            assert (pre[p+"bits_uop_robIdx_flag"],pre[p+"bits_uop_robIdx_value"],pre[p+"bits_uop_robIdx_isFormer"])==(
                int(req.uop.rob.flag),req.uop.rob.value,int(req.uop.rob.former))
            assert (pre[p+"bits_uop_sqIdx_first_flag"],pre[p+"bits_uop_sqIdx_second_flag"],pre[p+"bits_uop_sqIdx_value"])==(
                int(req.uop.sq.first),int(req.uop.sq.second),req.uop.sq.value)
            assert pre[p+"bits_uop_perfDebugInfo_runahead_checkpoint_id"]==req.uop.checkpoint
            grants[lq]=slot
        if len(grants)==120:break
    assert len(grants)==120 and set(grants.values())==set(range(120))
    for lq,slot in sorted(grants.items()):
        feedback=replace(reqs[lq],replay_feedback=True,slot=slot,need_replay=False,causes=0)
        await replay.cycle({lane:feedback},ready=(False,False,False))
    await replay.idle(12)
    assert not replay.observed[P.p_lqFull] and not replay.observed[P.p_replayAllocate]
    assert not any(replay.observed[P.io(f"replay_{b}_valid")] for b in range(3))
