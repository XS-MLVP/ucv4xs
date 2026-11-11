
import json
from pathlib import Path

import pytest

from suites.memblock.lsq.testbenches.psq.transactions import Address
from suites.memblock.lsq.testbenches.psq.transactions import Attributes
from suites.memblock.lsq.testbenches.psq.transactions import Data
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.vsq.transactions import Dispatch
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import cache
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import check_word
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import exception
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import finish_special
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import observation
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import rob as ident
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import sqptr
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import uncache
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import word
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import writeback
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import pair
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import requests
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import wait_valid
from suites.memblock.lsq.testbenches.store_queue.tests.helpers import write


@pytest.mark.parametrize("lane", (0, 1))
@pytest.mark.parametrize("memory", (1, 2, 7))
async def test_real_vsq_head_permissions_uncache_and_actual_owner_completion(sq, lane, memory):
    env = sq
    names = ("SQ-SPECIAL.nc" if memory == 1 else "SQ-SPECIAL.io", "SQ-PERMIT.precommit")
    env.begin(names)
    rob = RobPtr.encode(319, former=False)
    await env.cycle(dispatch=requests({lane * 7: (rob, 1)}), rob_head=rob)
    await env.cycle(dispatch=(Dispatch(),) * 8)
    address, data = Address(True, 0, 6, 0x120008, 0xABCD008, 3), Data(True, 0, 6, 0xFEDCBA9876543210)
    await write(env, address, data, lane=lane, attributes=Attributes(nc=memory == 1, mmio=memory != 1, memory=memory < 4))
    await wait_valid(env, "uncache_request")
    expected = observation(uncache_request=uncache(
        addr=address.paddr, vaddr=address.vaddr, data=data.data, mask=255, nc=int(memory == 1),
        memory_backed=int(memory < 4), rob_identity=ident(159, 1, 0)))
    env.expect(expected, "real VSQ supplies the special owner's ROB identity through PSQ")
    await env.idle(3)
    env.expect(expected, "actual integrated request remains stable while ready is low")
    await env.cycle(uncache_ready=True)
    env.expect(expected, "actual Uncache request fire", before=True)
    await env.idle(3, uncache_ack_valid=memory == 1, uncache_ack_to_load=True)
    env.expect(observation(sq_deq_ptr=sqptr(0), writeback=None, empty=0), "wrong-direction ack cannot complete this store")
    if memory == 1:
        await env.cycle(uncache_ack_valid=True, uncache_ack_to_load=False)
        await env.cycle(uncache_ack_valid=False)
    else:
        await env.cycle(uncache_response=True)
        wb = observation(writeback=writeback(rob_identity=ident(159, 1, 0), mmio=1,
                                             access_fault=0, bus_error=0))
        env.expect(wb, "actual response routed to original virtual owner's WB")
        await env.idle(3, uncache_response=False)
        env.expect(wb, "benign special WB keeps identity under stall")
        await env.cycle(writeback_ready=True)
        env.expect(wb, "actual special WB fire", before=True)
    await finish_special(env, 1)
    env.finish(names)


@pytest.mark.parametrize("cbo", range(4))
async def test_all_cbo_with_real_virtual_owner_and_completion_feedback(sq, cbo):
    env = sq
    names = ("SQ-SPECIAL.cbo",)
    env.begin(names)
    await env.cycle(dispatch=requests({3: (10, 1)}), rob_head=RobPtr.encode(10))
    await env.cycle(dispatch=(Dispatch(),) * 8)
    await write(env, Address(True, 0, cbo * 2 + 1, 0x18000, 0xABC000, 3), Data(True, 0, cbo * 2 + 1, (1 << 128) - 1))
    if cbo == 3:
        await wait_valid(env, "sbuffer_word_0")
        check_word(env, 0, 0x18000, 0xABC000, 0xFF, 0, wline=1)
        await env.cycle(sbuffer_ready=(True, True))
        check_word(env, 0, 0x18000, 0xABC000, 0xFF, 0, wline=1, before=True)
    else:
        await wait_valid(env, "cache_request")
        env.expect(observation(cache_request=cache(address=0xABC000, opcode=cbo, valid=None)), "real ROB-head CBO cache request")
        await env.idle(3)
        await env.cycle(cache_ready=True)
        await env.cycle(cache_response=True)
        await env.cycle(cache_response=False)
    if env.response.writeback is None:
        await wait_valid(env, "writeback")
    await env.cycle(writeback_ready=True)
    env.expect(observation(writeback=writeback(rob_identity=ident(10))), "original owner actual CBO WB fire", before=True)
    await finish_special(env, 1)
    env.finish(names)


@pytest.mark.parametrize("sq", (False,), indirect=True)
@pytest.mark.parametrize("hold", (0, 3))
@pytest.mark.parametrize("denied,corrupt", ((True, False), (False, True), (True, True)))
async def test_cache_error_through_real_vsq_identity_at_actual_wb_fire(sq, hold, denied, corrupt):
    """Explicit passive probe reaches actual fire, not a relaxed stage oracle."""
    env = sq
    names = ("SQ-SPECIAL.error_held" if hold else "SQ-SPECIAL.error_response",)
    env.begin(names)
    await env.cycle(dispatch=requests({7: (RobPtr.encode(319, former=False), 1)}), rob_head=RobPtr.encode(319, former=False))
    await env.cycle(dispatch=(Dispatch(),) * 8)
    await write(env, Address(True, 0, 3, (1 << 49) + 0x12340, 0xA12340, 3, hyper=True), Data(True, 0, 3, 0))
    await wait_valid(env, "cache_request")
    await env.cycle(cache_ready=True)
    await env.cycle(cache_response=True, cache_denied=denied, cache_corrupt=corrupt)
    wb = observation(writeback=writeback(rob_identity=ident(159, 1, 0), access_fault=int(denied), bus_error=int(corrupt)),
                     exception_info=exception(vaddr=(1 << 49) + 0x12340, hyper=1, valid=None))
    env.expect(wb, "real cache response reports original error/ROB/VA identity")
    await env.idle(hold, cache_response=False, cache_denied=False, cache_corrupt=False)
    await env.cycle(cache_response=False, cache_denied=False, cache_corrupt=False, writeback_ready=True)
    env.expect(wb, "actual integrated WB fire must retain the accepted response fault", before=True)
    await finish_special(env, 1)
    env.finish(names)


@pytest.mark.parametrize("sq", (False,), indirect=True)
@pytest.mark.parametrize("old_queued", (False, True))
async def test_real_vsq_rob_head_zero_must_write_its_own_line_before_wb(sq, old_queued):
    env = sq
    names = ("SQ-SPECIAL.zero_owner",) if old_queued else ("SQ-SPECIAL.cbo",)
    env.begin(names)
    if old_queued:
        await env.cycle(dispatch=requests({0: (10, 1)}))
        await env.cycle(dispatch=(Dispatch(),) * 8)
        await write(env, Address(True, 0, 6, 0x10000, 0xABC000, 3), Data(True, 0, 6, 0x1122334455667788))
        await wait_valid(env, "sbuffer_word_0", rob_head=RobPtr.encode(11))
        env.expect(observation(sbuffer_word_0=word(wline=0, valid=None), sq_deq_ptr=sqptr(0)),
                   "older retired normal store remains in real child queue")
    slot = int(old_queued)
    await env.cycle(dispatch=requests({7: (11, 1)}, start=slot), rob_head=RobPtr.encode(11))
    await env.cycle(dispatch=(Dispatch(),) * 8)
    await write(env, Address(True, slot, 7, 0x20000, 0xDEF000, 3), Data(True, slot, 7, (1 << 128) - 1))
    await env.idle(10)
    fires, wb = [], None
    for _ in range(30):
        await env.cycle(sbuffer_ready=(True, True), writeback_ready=True)
        pre = env.pre_response
        for lane, issued in enumerate((pre.sbuffer_word_0, pre.sbuffer_word_1)):
            if issued is not None:
                fires.append({"tick": env.last_tick, "vaddr": issued.vaddr, "addr": issued.addr,
                              "wline": issued.wline, "data": issued.data, "mask": issued.mask})
        if pre.writeback is not None:
            assert pre.writeback.rob.value == 11
            wb = env.last_tick
            break
    assert wb is not None
    await finish_special(env, slot + 1)
    zero = [fire for fire in fires if fire["vaddr"] == 0x20000 and fire["addr"] == 0xDEF000 and fire["wline"] == 1 and fire["data"] == 0]
    evidence = {"nodeid": env.nodeid, "old_queued": old_queued, "real_vsq_rob_head": 11, "sbuffer_fires": fires,
                "actual_wb_tick": wb, "actual_sq_release_tick": env.last_tick, "actual_sq_deq": slot + 1,
                "actual_zero_transfers_before_wb": len(zero), "required_zero_transfers": 1}
    Path(env.journal.name).with_name("zero-owner-check.json").write_text(json.dumps(evidence, indent=2) + "\n")
    assert len(zero) == 1, ("real VSQ permits zero WB/SQ release without its own zero write", evidence)
    env.finish(names)


@pytest.mark.parametrize("sq", (False,), indirect=True)
@pytest.mark.parametrize("memory", (1, 2, 7))
async def test_later_special_finish_cannot_release_an_unconsumed_ordinary_head(sq, memory):
    env = sq
    names = ("SQ-CREDIT.special_order",)
    env.begin(names)
    await env.cycle(dispatch=requests({0: (10, 1), 7: (11, 1)}))
    await env.cycle(dispatch=(Dispatch(),) * 8)
    await write(env, Address(True, 0, 6, 0x30000, 0xABC000, 3), Data(True, 0, 6, 0x8877665544332211))
    await wait_valid(env, "sbuffer_word_0", rob_head=RobPtr.encode(11))
    await write(env, Address(True, 1, 6, 0x40000, 0xDEF000, 3), Data(True, 1, 6, 0x1111222233334444), lane=1,
                attributes=Attributes(nc=memory == 1, mmio=memory != 1, memory=memory < 4))
    await wait_valid(env, "uncache_request")
    env.expect(observation(uncache_request=uncache(addr=0xDEF000, rob_identity=ident(11), valid=None), sq_deq_ptr=sqptr(0)),
               "real ROB-head special is issued while older retired ordinary request is still unconsumed")
    await env.cycle(uncache_ready=True)
    if memory == 1:
        await env.cycle(uncache_ack_valid=True)
        await env.cycle(uncache_ack_valid=False)
    else:
        await env.cycle(uncache_response=True)
        await env.cycle(uncache_response=False, writeback_ready=True)
        env.expect(observation(writeback=writeback(rob_identity=ident(11))), "actual younger IO WB completed", before=True)
        await env.cycle(writeback_ready=False)
    pre, post = env.pre_response, env.response
    def position(pointer):
        return int(pointer.first) * 128 + int(pointer.second) * 64 + pointer.value
    older = post.sbuffer_word_0
    older_va = older.vaddr if older is not None else None
    evidence = {"nodeid": env.nodeid, "memory_type": memory, "tick": env.last_tick,
                "head_before": position(pre.sq_deq_ptr), "head_after": position(post.sq_deq_ptr),
                "older_write_still_valid": older is not None, "older_write_va": older_va,
                "sbuffer_ready": list(env.controls.sbuffer_ready),
                "actual_sq_release_valid": post.dequeue_valid,
                "actual_sq_release_count": post.dequeue_count, "required_head": 0}
    Path(env.journal.name).with_name("special-order-check.json").write_text(json.dumps(evidence, indent=2) + "\n")
    assert position(post.sq_deq_ptr) == 0, ("young special completion released an unconsumed older ordinary owner", evidence)
    await env.cycle(sbuffer_ready=(True, True))
    check_word(env, 0, 0x30000, 0xABC000, 0xFF, 0x8877665544332211, before=True)
    await finish_special(env, 2)
    env.finish(names)
