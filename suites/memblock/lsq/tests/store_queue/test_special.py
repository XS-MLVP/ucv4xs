import json
from pathlib import Path

import pytest

from lsqverify.psq.checks import check_word, ptr_values
from lsqverify.psq.types import Address, Attributes, Data
from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import RobPtr
from lsqverify.vsq.types import Dispatch
from .helpers import finish_special, pair, requests, wait_valid, write


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
    await wait_valid(env, "io_toUncacheBuffer_req_valid")
    expected = {"io_toUncacheBuffer_req_valid": 1, "io_toUncacheBuffer_req_bits_addr": address.paddr,
                "io_toUncacheBuffer_req_bits_vaddr": address.vaddr, "io_toUncacheBuffer_req_bits_data": data.data,
                "io_toUncacheBuffer_req_bits_mask": 255, "io_toUncacheBuffer_req_bits_nc": int(memory == 1),
                "io_toUncacheBuffer_req_bits_memBackTypeMM": int(memory < 4), "io_toUncacheBuffer_req_bits_robIdx_flag": 1,
                "io_toUncacheBuffer_req_bits_robIdx_value": 159, "io_toUncacheBuffer_req_bits_robIdx_isFormer": 0}
    env.expect(expected, "real VSQ supplies the special owner's ROB identity through PSQ")
    await env.idle(3)
    env.expect(expected, "actual integrated request remains stable while ready is low")
    await env.cycle(uncache_ready=True)
    env.expect(expected, "actual Uncache request fire", before=True)
    await env.idle(3, uncache_ack_valid=memory == 1, uncache_ack_to_load=True)
    env.expect({**ptr_values("io_sqDeqPtr_", 0), "io_writeBack_valid": 0, "io_sqEmpty": 0}, "wrong-direction ack cannot complete this store")
    if memory == 1:
        await env.cycle(uncache_ack_valid=True, uncache_ack_to_load=False)
        await env.cycle(uncache_ack_valid=False)
    else:
        await env.cycle(uncache_response=True)
        wb = {"io_writeBack_valid": 1, "io_writeBack_bits_robIdx_flag": 1, "io_writeBack_bits_robIdx_value": 159,
              "io_writeBack_bits_robIdx_isFormer": 0, "io_writeBack_bits_debugInfo_isMMIO": 1,
              "io_writeBack_bits_exceptionVec_7": 0, "io_writeBack_bits_exceptionVec_19": 0}
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
        await wait_valid(env, "io_writeToSbuffer_req_0_valid")
        check_word(env, 0, 0x18000, 0xABC000, 0xFF, 0, wline=1)
        await env.cycle(sbuffer_ready=(True, True))
        check_word(env, 0, 0x18000, 0xABC000, 0xFF, 0, wline=1, before=True)
    else:
        await wait_valid(env, "io_toDCache_req_valid")
        env.expect({"io_toDCache_req_bits_opcode": cbo, "io_toDCache_req_bits_address": 0xABC000}, "real ROB-head CBO cache request")
        await env.idle(3)
        await env.cycle(cache_ready=True)
        await env.cycle(cache_response=True)
        await env.cycle(cache_response=False)
    if not env.observed["io_writeBack_valid"]:
        await wait_valid(env, "io_writeBack_valid")
    await env.cycle(writeback_ready=True)
    env.expect({"io_writeBack_valid": 1, "io_writeBack_bits_robIdx_value": 10}, "original owner actual CBO WB fire", before=True)
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
    await wait_valid(env, "io_toDCache_req_valid")
    await env.cycle(cache_ready=True)
    await env.cycle(cache_response=True, cache_denied=denied, cache_corrupt=corrupt)
    wb = {"io_writeBack_valid": 1, "io_writeBack_bits_robIdx_flag": 1, "io_writeBack_bits_robIdx_value": 159,
          "io_writeBack_bits_robIdx_isFormer": 0, "io_writeBack_bits_exceptionVec_7": int(denied), "io_writeBack_bits_exceptionVec_19": int(corrupt),
          "io_exceptionInfo_valid": 1, "io_exceptionInfo_bits_vaddr": (1 << 49) + 0x12340, "io_exceptionInfo_bits_isHyper": 1}
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
        await wait_valid(env, "io_writeToSbuffer_req_0_valid", rob_head=RobPtr.encode(11))
        env.expect({"io_writeToSbuffer_req_0_bits_wline": 0, **ptr_values("io_sqDeqPtr_", 0)}, "older retired normal store remains in real child queue")
    slot = int(old_queued)
    await env.cycle(dispatch=requests({7: (11, 1)}, start=slot), rob_head=RobPtr.encode(11))
    await env.cycle(dispatch=(Dispatch(),) * 8)
    await write(env, Address(True, slot, 7, 0x20000, 0xDEF000, 3), Data(True, slot, 7, (1 << 128) - 1))
    await env.idle(10)
    fires, wb = [], None
    for _ in range(30):
        await env.cycle(sbuffer_ready=(True, True), writeback_ready=True)
        pre = env.pre_observed
        for lane in range(2):
            p = f"io_writeToSbuffer_req_{lane}_"
            if pre[p + "valid"]:
                fires.append({"tick": env.last_tick, **{key: pre[p + "bits_" + key] for key in ("vaddr", "addr", "wline", "data", "mask")}})
        if pre["io_writeBack_valid"]:
            assert pre["io_writeBack_bits_robIdx_value"] == 11
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
    await wait_valid(env, "io_writeToSbuffer_req_0_valid", rob_head=RobPtr.encode(11))
    await write(env, Address(True, 1, 6, 0x40000, 0xDEF000, 3), Data(True, 1, 6, 0x1111222233334444), lane=1,
                attributes=Attributes(nc=memory == 1, mmio=memory != 1, memory=memory < 4))
    await wait_valid(env, "io_toUncacheBuffer_req_valid")
    env.expect({"io_toUncacheBuffer_req_bits_robIdx_value": 11, "io_toUncacheBuffer_req_bits_addr": 0xDEF000,
                **ptr_values("io_sqDeqPtr_", 0)}, "real ROB-head special is issued while older retired ordinary request is still unconsumed")
    await env.cycle(uncache_ready=True)
    if memory == 1:
        await env.cycle(uncache_ack_valid=True)
        await env.cycle(uncache_ack_valid=False)
    else:
        await env.cycle(uncache_response=True)
        await env.cycle(uncache_response=False, writeback_ready=True)
        env.expect({"io_writeBack_valid": 1, "io_writeBack_bits_robIdx_value": 11}, "actual younger IO WB completed", before=True)
        await env.cycle(writeback_ready=False)
    pre, post = env.pre_observed, env.observed
    from lsqverify.psq.checks import read_ptr
    evidence = {"nodeid": env.nodeid, "memory_type": memory, "tick": env.last_tick, "head_before": read_ptr(pre), "head_after": read_ptr(post),
                "older_write_still_valid": post["io_writeToSbuffer_req_0_valid"], "older_write_va": post["io_writeToSbuffer_req_0_bits_vaddr"],
                "sbuffer_ready": list(env.controls.sbuffer_ready), "actual_sq_release_valid": post["io_toLsqEnqCtrl_sqDeq_valid"],
                "actual_sq_release_count": post["io_toLsqEnqCtrl_sqDeq_bits"], "required_head": 0}
    Path(env.journal.name).with_name("special-order-check.json").write_text(json.dumps(evidence, indent=2) + "\n")
    assert read_ptr(post) == 0, ("young special completion released an unconsumed older ordinary owner", evidence)
    await env.cycle(sbuffer_ready=(True, True))
    check_word(env, 0, 0x30000, 0xABC000, 0xFF, 0x8877665544332211, before=True)
    await finish_special(env, 2)
    env.finish(names)
