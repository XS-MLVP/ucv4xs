"""NoSpec/BlockBack-normal CBO: clean lifecycle and retained real fault domains."""
from dataclasses import replace

import pytest

from lsqverify.lsq_wrapper.types import Dispatch
from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import RobPtr
from .normal_owners import NormalCboStore
from .serialized_cbo_owners import SerializedCboOwners
from .special_owners import SpecialOwners, SpecialStore
from .test_special_memory import outcome


@pytest.mark.parametrize("sta_lane",range(2))
async def test_serialized_cbo_all_physical_slots_original_WB_retire_then_younger_Load(lsq,sta_lane):
    visits=set()
    for pos in range(256):
        opcode=pos//64
        owner=NormalCboStore(pos,RobPtr.encode(10+2*pos,former=not bool(pos&1)),0x400000+pos*64,0xB400000+pos*64,
                             size=4,value=0x112233445566778899AABBCC00000000+pos,cbo=opcode,hyper=bool(pos&1))
        trace=SerializedCboOwners(lsq,[owner],start=pos,load_position=pos,initial_head=owner.rob)
        await trace.allocate()
        await trace.write(pos,lane=sta_lane)
        await trace.cache_roundtrip(pos,hold=pos%4)
        await trace.retire_then_load()
        await trace.finish()
        assert not trace.effect_errors
        visits.add((pos%64,opcode))
    assert len(visits)==256
    lsq.prove("LSQ-RETIRE.cbo","LSQ-ALLOC.sq_wrap","LSQ-ALLOC.lq_wrap")


@pytest.mark.parametrize("hold",(0,3))
@pytest.mark.parametrize("denied,corrupt",((True,False),(False,True),(True,True)))
async def test_serialized_cbo_actual_fault_WB_preserves_original_response_without_younger_dispatch(lsq_probe,hold,denied,corrupt):
    owner=NormalCboStore(0,RobPtr.encode(10,former=False),(1<<49)+0x12340,0xA12340,
                         size=4,cbo=1,hyper=True)
    trace=SerializedCboOwners(lsq_probe,[owner],initial_head=owner.rob)
    await trace.allocate()
    await trace.write(0,lane=1)
    wb=await trace.cache_roundtrip(0,denied=denied,corrupt=corrupt,hold=hold)
    report=outcome(trace,"serialized_CBO_actual_fault_fire",expected_denied=denied,expected_corrupt=corrupt,hold=hold,
                   normal_empty_ROB_CBO_dispatch=True,younger_Load_dispatches=0,full_cycle_reference_compared=False)
    assert (wb["denied"],wb["corrupt"])==(int(denied),int(corrupt)),("serialized CBO lost original fault at actual WB.fire",report)
    await trace.idle(8)
    assert trace.head==1 and lsq_probe.observed["io_lqEmpty"]
    # The CBO has an exception. No younger dispatch/architectural retirement
    # is fabricated, and protocol probes NEVER earn a full-output checked bin.


async def zero_with_retired_old(env,old_queued):
    old=SpecialStore(0,RobPtr.encode(10),0x10000,0xABC000,value=0x1122334455667788)
    pos=int(old_queued)
    zero=NormalCboStore(pos,RobPtr.encode(11),0x20000,0xDEF000,size=4,value=(1<<128)-1,cbo=3)
    trace=SpecialOwners(env,[old,zero] if old_queued else [zero],initial_head=old.rob if old_queued else zero.rob)
    if old_queued:
        await trace.cycle(dispatch=(Dispatch(True,2,old.rob,1,store_end=SqPtr.encode(1)),)+(Dispatch(),)*7)
        await trace.write(0)
        trace.activate(pos)
        await trace.idle(8)
        await trace.wait("io_sbuffer_req_0_valid")
        assert not trace.fires
    # Earlier ordinary Store is ROB-retired but its physical Sbuffer fragment
    # remains. This is a real normal empty-ROB CBO dispatch, not read==head.
    await trace.cycle(dispatch=(Dispatch(True,2,zero.rob,1,store_end=SqPtr.encode(pos+1)),)+(Dispatch(),)*7)
    await trace.write(pos,lane=1)
    await trace.idle(10)
    trace.base=replace(trace.base,sbuffer_ready=(True,True),writeback_ready=True)
    await trace.wait("io_mmioStout_valid")
    await trace.cycle()
    assert any(w["position"]==pos for w in trace.wbs)
    await trace.idle(8)
    own=[f for f in trace.fires if f["position"]==pos and f["actual"]["wline"] and f["actual"]["mask"]==65535 and f["actual"]["data"]==0]
    report=outcome(trace,"serialized_zero_original_effects",old_queued=old_queued,own_zero16_fires=len(own),
                   normal_empty_ROB_CBO_dispatch=True,no_younger_dispatch=True)
    assert len(own)==1,("serialized zero WB/release without its own zero16 transfer",report)
    assert trace.head==pos+1 and not trace.effect_errors


@pytest.mark.parametrize("old_queued",(False,True))
async def test_serialized_zero_retired_old_sbuffer_still_requires_own_zero16_strict(lsq,old_queued):
    await zero_with_retired_old(lsq,old_queued)


@pytest.mark.parametrize("old_queued",(False,True))
async def test_serialized_zero_retired_old_sbuffer_actual_WB_and_release_protocol_only(lsq_probe,old_queued):
    await zero_with_retired_old(lsq_probe,old_queued)
