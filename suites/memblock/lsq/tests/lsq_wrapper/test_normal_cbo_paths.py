"""Real StoreUnit QB CBO at all slots/flags, preserving legacy interface tests."""
import pytest

from lsqverify.vlq.types import RobPtr
from .normal_owners import NormalCboStore
from .special_owners import SpecialOwners


@pytest.mark.parametrize("sta_lane",range(2))
async def test_normal_cbo_each_slot_all_opcodes_real_zero16_or_cache_and_wb(lsq,sta_lane):
    visits=set()
    for position in range(256):
        opcode=position//64
        store=NormalCboStore(position,RobPtr.encode(10+2*position,former=not bool(position&1)),
                             0x400000+position*64,0xB400000+position*64,size=4,
                             value=0x112233445566778899AABBCC00000000+position,cbo=opcode,hyper=bool(position&1))
        trace=SpecialOwners(lsq,[store],start=position,load_position=position,initial_head=store.rob)
        await trace.allocate()
        await trace.write(position,lane=sta_lane)
        wb=await trace.cache_roundtrip(position,hold=position%4)
        assert wb["denied"]==wb["corrupt"]==0 and wb["vaddr"]==store.vaddr and wb["hyper"]==int(store.hyper)
        assert len(trace.cache_requests)==len(trace.cache_responses)==int(opcode!=3)
        assert len(trace.fires)==int(opcode==3)
        if opcode==3:
            assert trace.fires[0]["actual"]["mask"]==65535 and trace.fires[0]["actual"]["data"]==0
        await trace.finish()
        visits.add((position%64,opcode))
    assert visits=={(slot,opcode) for slot in range(64) for opcode in range(4)}
    lsq.prove("LSQ-RETIRE.cbo","LSQ-ALLOC.sq_wrap","LSQ-ALLOC.lq_wrap")
