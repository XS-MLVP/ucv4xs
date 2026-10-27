"""Original RAW records live until the Load's exclusive address boundary."""
import pytest

from lsqverify.vlq.types import RobPtr


@pytest.mark.parametrize("start",(0,63,255))
@pytest.mark.parametrize("distance",(127,128))
@pytest.mark.parametrize("lane",range(3))
async def test_RAW_exclusive_tail_retains_until_address_prefix_and_then_no_stale_identity(raw,start,distance,lane):
    await raw.advance_head(start)
    end=start+distance
    query=raw.request(end,0xA10000,rob=RobPtr.encode(20),tag=85)
    await raw.cycle({lane:query})
    await raw.probe({0:raw.store(query.paddr,rob=RobPtr.encode(19),tag=99)},expect={0:query})
    await raw.advance_head(end-1)
    await raw.probe({1:raw.store(query.paddr,rob=RobPtr.encode(19),tag=98)},expect={1:query})
    await raw.advance_head(end)
    await raw.probe({0:raw.store(query.paddr,rob=RobPtr.encode(19)),1:raw.store(query.paddr,rob=RobPtr.encode(19))},expect={0:None,1:None})
    await raw.idle(72)
    assert not raw.observed.full and raw.observed.ready==(True,True,True)


@pytest.mark.parametrize("lane",range(3))
async def test_RAW_full56_exact128_release_and_new_original_generation_every_record(raw,lane):
    async def fill_and_check(end,base,pa):
        queries=[raw.request(end,pa+16*i,rob=RobPtr.encode(base+i),tag=64+i) for i in range(56)]
        for query in queries:await raw.cycle({lane:query})
        assert raw.observed.full
        refused=raw.request(end,pa+0x1000,rob=RobPtr.encode(base+56),tag=127)
        await raw.cycle({lane:refused})
        assert not raw.observed.ready[lane]
        for i in range(0,56,2):
            await raw.probe({j:raw.store(queries[i+j].paddr,rob=RobPtr.encode(base-1),tag=90+j) for j in range(2)},
                            expect={j:queries[i+j] for j in range(2)})
        await raw.probe({0:raw.store(refused.paddr,rob=RobPtr.encode(base-1))},expect={0:None})
        return queries
    old=await fill_and_check(128,10,0xB00000)
    await raw.advance_head(127)
    await raw.probe({0:raw.store(old[0].paddr,rob=RobPtr.encode(9)),1:raw.store(old[-1].paddr,rob=RobPtr.encode(9))},expect={0:old[0],1:old[-1]})
    await raw.advance_head(128)
    await raw.idle(72)
    assert not raw.observed.full
    fresh=await fill_and_check(256,80,0xC00000)
    for i in range(0,56,2):
        await raw.probe({j:raw.store(old[i+j].paddr,rob=RobPtr.encode(79)) for j in range(2)},expect={0:None,1:None})
    await raw.advance_head(256)
    await raw.idle(72)
    for i in range(0,56,2):
        await raw.probe({j:raw.store(fresh[i+j].paddr,rob=RobPtr.encode(79)) for j in range(2)},expect={0:None,1:None})
    assert not raw.observed.full and raw.observed.ready==(True,True,True)
