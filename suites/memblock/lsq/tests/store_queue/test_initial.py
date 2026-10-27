import pytest

from lsqverify.forward.types import Query, Translation
from lsqverify.psq.checks import ptr_values
from lsqverify.psq.directed import scalar_word
from lsqverify.psq.types import Address, Data
from lsqverify.raw.types import SqPtr
from lsqverify.store_queue.directed import consume
from lsqverify.vlq.types import RobPtr
from lsqverify.vsq.types import Dispatch


@pytest.mark.parametrize("lane", (0, 7))
@pytest.mark.parametrize("flows", (1, 3))
@pytest.mark.parametrize("permit", ("precommit", "retired"))
async def test_real_vsq_to_psq_writeout_and_physical_release_feedback(sq, lane, flows, permit):
    env = sq
    names = ("SQ-PERMIT.none", "SQ-PERMIT." + permit, "SQ-READY.independent", "SQ-WRITE.lanes", "SQ-FORWARD.data", "SQ-DISPATCH.sparse")
    if flows > 1:
        names += ("SQ-DISPATCH.multi", "SQ-CREDIT.last_flow")
    if permit == "retired":
        names += ("SQ-RETIRE.buffered",)
    env.begin(names)
    dispatch = tuple(Dispatch(True, True, RobPtr.encode(10), flows, SqPtr.encode(flows)) if i == lane else Dispatch() for i in range(8))
    await env.cycle(dispatch=dispatch)
    await env.cycle(dispatch=(Dispatch(),) * 8)
    owners = [(Address(True, index, 6, 0x100008 + index * 4096, 0xA000008 + index * 4096, 3),
               Data(True, index, 6, 0x8877665544332200 + index)) for index in range(flows)]
    write_lane = int(lane == 7)
    for address, data in owners:
        await env.cycle(addresses=tuple(address if i == write_lane else Address() for i in range(2)))
        await env.cycle(addresses=(Address(), Address()), data=tuple(data if i != write_lane else Data() for i in range(2)))
        await env.cycle(data=(Data(), Data()))
    await env.idle(5)
    env.expect({"io_writeToSbuffer_req_0_valid": 0, "io_toLsqEnqCtrl_sqDeq_valid": 0, "io_sqEmpty": 0,
                **ptr_values("io_toLoadQueue_stAddrReadySqPtr_", flows), **ptr_values("io_toLoadQueue_stDataReadySqPtr_", flows)},
               "real VSQ has no ROB-head/retired permission yet, despite complete physical bytes")
    address, data = owners[-1]
    await env.cycle(queries=(Query(True, address.vaddr, SqPtr.encode(flows), 3),) * 3)
    await env.cycle(queries=(Query(),) * 3, translations=(Translation(address.paddr),) * 3)
    expected = {}
    for load_lane in range(3):
        prefix = f"io_forward_{load_lane}_s2Resp_"
        expected.update({prefix + "valid": 1, prefix + "bits_matchInvalid": 0, prefix + "bits_forwardInvalid": 0,
                         prefix + "bits_dataInvalid_valid": 0, prefix + "bits_addrInvalid_valid": 0})
        expected.update({prefix + f"bits_forwardMask_{byte}": int(byte >= 8) for byte in range(16)})
        expected.update({prefix + f"bits_forwardData_{byte + 8}": data.data >> (8 * byte) & 255 for byte in range(8)})
    env.expect(expected, "original STA/STD bytes reach all three actual integrated forward lanes")
    await env.idle(12, rob_head=RobPtr.encode(10 if permit == "precommit" else 11))
    env.expect({"io_writeToSbuffer_req_0_valid": 1, "io_sqEmpty": 0, **ptr_values("io_sqDeqPtr_", 0)},
               "real VSQ permission reaches real PSQ, but buffered writes are not yet completed")
    await consume(env, [scalar_word(*owner) for owner in owners], flows)
    env.finish(names)


async def test_combined_initial_empty_reset_has_no_phantom_credit(sq):
    env = sq
    names = ("SQ-RESET.initial",)
    env.begin(names)
    env.expect({"io_sqEmpty": 1, "io_sqFull": 0, "io_toLsqEnqCtrl_sqDeq_valid": 0, "io_toLsqEnqCtrl_sqRedirectPtr_valid": 0,
                "io_toLsqEnqCtrl_sqRecoverStall": 0, **ptr_values("io_sqDeqPtr_", 0), **ptr_values("io_physicalUpperSqIdx_", 64)},
               "both real queues converge empty without fabricated dynamic WFI/inactive ports")
    env.finish(names)
