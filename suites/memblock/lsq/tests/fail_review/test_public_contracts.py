"""Small semantic oracles, deliberately independent of the existing models."""
from dataclasses import replace

import pytest

from lsqverify.deq.types import Inputs as DeqInputs, Store, encode as deq_encode
from lsqverify.raw.types import SqPtr
from lsqverify.replay.codec import encode as replay_encode
from lsqverify.replay.types import Cause, Enqueue, Inputs as ReplayInputs, Uop
from lsqverify.vlq.types import QueuePtr, RobPtr


@pytest.mark.parametrize("review_dut", ["load_queue_uncache"], indirect=True)
@pytest.mark.parametrize("mode", ("reuse_unconsumed", "different_sid", "consume_first"))
@pytest.mark.parametrize("new_error", (False, True))
async def test_returned_SID_cannot_rewrite_original_response(review_dut, mode, new_error):
    e = review_dut
    e.metadata = dict(issue="LQU-SID-001", mode=mode, new_error=new_error,
        domain="Normal NC LQU input projection; native Uncache allocator and full LoadUnit not instantiated")
    base = {"io_rob_pendingPtr_value": 10, "io_rob_pendingPtr_isFormer": 1}
    a, b = dict(uid=1, rob=10, lq=11, va=0x10000, pa=0x80000000), dict(uid=2, rob=11, lq=12, va=0x11000, pa=0x80001000)
    data_a, data_b = 0x0123456789ABCDEF, 0xFEDCBA9876543210
    active_sids = {}

    async def cycle(fields=None):
        await e.step({**base, **(fields or {})})

    async def enqueue(owner, lane):
        p = f"io_req_{lane}_"
        fields = {"valid": 1, "bits_uop_robIdx_value": owner["rob"], "bits_uop_robIdx_isFormer": 1,
            "bits_uop_lqIdx_value": owner["lq"], "bits_uop_ftqOffset": 2 * owner["uid"] - 1,
            "bits_uop_perfDebugInfo_runahead_checkpoint_id": owner["uid"],
            "bits_vaddr": owner["va"], "bits_fullva": owner["va"], "bits_paddr": owner["pa"],
            "bits_mask": 255, "bits_nc": 1, "bits_rep_info_need_rep": 1, "bits_rep_info_cause_0": 1}
        await cycle({p + name: value for name, value in fields.items()})
        e.check("LQU valid input actually sampled", e.input[p + "valid"], 1)
        e.event("LDU_S3_input", **owner, mask=255, cause="C_UNCACHE", fullVA=owner["va"], input_lane=lane)

    async def take_and_bind(owner, sid):
        for _ in range(40):
            if e.post["io_uncache_req_valid"]:
                break
            await cycle()
        e.check("external request available", e.post["io_uncache_req_valid"], 1)
        await cycle({"io_uncache_req_ready": 1})
        e.check("request actual fire", e.pre["io_uncache_req_valid"], 1)
        actual = {name: e.pre["io_uncache_req_bits_" + name] for name in ("addr", "vaddr", "mask", "nc", "robIdx_value")}
        e.check("bus owner", actual, dict(addr=owner["pa"], vaddr=owner["va"], mask=255, nc=1, robIdx_value=owner["rob"]))
        mid = e.pre["io_uncache_req_bits_id"]
        e.event("bus_request_fire", uid=owner["uid"], mid=mid, **actual)
        assert sid not in active_sids, "SID reuse only after original external response was returned"
        active_sids[sid] = owner["uid"]
        await cycle({"io_uncache_idResp_valid": 1, "io_uncache_idResp_bits_mid": mid, "io_uncache_idResp_bits_sid": sid})
        e.event("SID_ack", uid=owner["uid"], mid=mid, sid=sid)

    async def respond(owner, sid, data, error):
        assert active_sids.pop(sid) == owner["uid"]
        await cycle({"io_uncache_resp_valid": 1, "io_uncache_resp_bits_id": sid,
            "io_uncache_resp_bits_data": data, "io_uncache_resp_bits_error": error})
        e.check("external response valid actually sampled", e.input["io_uncache_resp_valid"], 1)
        e.event("response_valid_SID_returned", uid=owner["uid"], sid=sid, data=data, error=error,
            response_ready_not_retained=True, acceptance_confirmed_by_following_original_LQ_wakeup=True)
        for _ in range(40):
            if ("nc", 0, owner["lq"]) in e.wakes:
                break
            await cycle()
        e.check("original LQ wakeup", ("nc", 0, owner["lq"]) in e.wakes, True)

    async def consume(owner, data, error):
        p = "io_bypass_1_"
        await cycle({p + "s0Req_valid": 1, p + "s0Req_bits_lqIdx_value": owner["lq"], p + "s0Req_bits_isNCReplay": 1})
        e.check("defined s1 response", e.post[p + "s1Resp_valid"], 1)
        e.check("s1 PA belongs to original UID", e.post[p + "s1Resp_bits_paddr"], owner["pa"])
        s1_error = e.post["io_exceptionInfo_bits_exceptionVec_19"]
        e.check("exception event valid", e.post["io_exceptionInfo_valid"], 1)
        e.event("original_UID_s1_consume", uid=owner["uid"], original_PA=owner["pa"], actual_error=s1_error)
        await cycle()
        e.check("defined s2 response", e.post[p + "s2Resp_valid"], 1)
        actual = dict(data=e.post[p + "s2Resp_bits_data"], derr=e.post[p + "s2Resp_bits_derr"],
            nderr=e.post[p + "s2Resp_bits_nderr"], s1_error=s1_error)
        expected = dict(data=data * ((1 << 64) + 1), derr=int(error), nderr=0, s1_error=int(error))
        e.event("original_UID_s2_response", uid=owner["uid"], **actual)
        e.check("original response preserved at actual consumption", actual, expected, fatal=False)
        await cycle()

    await enqueue(a, 0)
    await take_and_bind(a, 3)
    await respond(a, 3, data_a, False)
    if mode == "consume_first":
        await consume(a, data_a, False)
    await enqueue(b, 1)
    sid_b = 4 if mode == "different_sid" else 3
    await take_and_bind(b, sid_b)
    await respond(b, sid_b, data_b, new_error)
    if mode != "consume_first":
        await consume(a, data_a, False)
    await consume(b, data_b, new_error)
    await e.idle(5, base)
    e.check("all external responses returned", active_sids, {})
    e.finish()


@pytest.mark.parametrize("review_dut", ["deq_module"], indirect=True)
@pytest.mark.parametrize("stall", (0, 3))
@pytest.mark.parametrize("denied,corrupt", ((True, False), (False, True), (True, True)))
async def test_CBO_fault_belongs_to_actual_writeback_fire(review_dut, stall, denied, corrupt):
    e = review_dut
    e.metadata = dict(issue="DEQ-WB-001", stall=stall, denied=denied, corrupt=corrupt,
        domain="Committed CBO Deq public interface; full Backend arbitration reachability is separate")
    owner = Store(vaddr=0x12340, page=0xABC, byte_mask=15, data=0x11223344,
        data_valid=True, address_valid=True, committed=True, cache_operation=True, cbo=0)
    packet = DeqInputs(stores=(owner, Store()), valid_count=1)

    async def cycle(**changes):
        await e.step(deq_encode(replace(packet, **changes)))

    await cycle()
    for _ in range(30):
        if e.post["io_toDCache_req_valid"]:
            break
        await cycle()
    e.check("Cache request offered", e.post["io_toDCache_req_valid"], 1)
    await cycle(cache_ready=True)
    e.check("Cache request actual fire", e.pre["io_toDCache_req_valid"], 1)
    e.check("original CBO PA", e.pre["io_toDCache_req_bits_address"], owner.paddr)
    e.event("Cache_request_fire", uid=1, PA=owner.paddr, CBO_operation=0, committed=True)
    await cycle(cache_response=True, cache_denied=denied, cache_corrupt=corrupt)
    e.check("Cache response actual fire", e.pre["io_toDCache_resp_ready"], 1)
    e.event("Cache_response_fire", uid=1, denied=denied, corrupt=corrupt, writeback_ready=False)
    wanted = dict(valid=1, denied=int(denied), corrupt=int(corrupt))

    def payload(out):
        return dict(valid=out["io_writeBack_valid"], denied=out["io_writeBack_bits_exceptionVec_7"],
            corrupt=out["io_writeBack_bits_exceptionVec_19"])

    e.check("first defined WB error", payload(e.post), wanted)
    for index in range(stall):
        await cycle()
        e.event("held_writeback", index=index, ready=False, **payload(e.post))
        e.check("valid WB payload stable under backpressure", payload(e.post), wanted, fatal=False)
    await cycle(writeback_ready=True)
    e.event("WB_actual_fire", uid=1, ready=True, **payload(e.pre))
    e.check("WB actual fire remains valid", e.pre["io_writeBack_valid"], 1)
    e.check("accepted original errors reach WB fire", payload(e.pre), wanted, fatal=False)
    await e.step(deq_encode(DeqInputs()))
    e.finish()


@pytest.mark.parametrize("review_dut", ["load_queue_rar"], indirect=True)
@pytest.mark.parametrize("distance", range(4))
@pytest.mark.parametrize("data_valid", (False, True))
async def test_RAR_release_association_has_the_declared_age_window(review_dut, distance, data_valid):
    e = review_dut
    e.metadata = dict(issue="RAR-REL-001", distance=distance, data_valid=data_valid,
        domain="RAR current/previous release association contract; expired extra replay alone is not an ISA-data-error proof")
    if distance:
        await e.step({"io_release_valid": 1, "io_release_bits_paddr": 0x18007})
        e.event("release", PA=0x18007)
        await e.idle(distance - 1)
    p = "io_query_0_req_"
    fields = {p + "valid": 1, p + "bits_robIdx_value": 2, p + "bits_robIdx_isFormer": 1,
        p + "bits_lqIdx_value": 2, p + "bits_paddr": 0x18000, p + "bits_dataValid": int(data_valid)}
    if distance == 0:
        fields.update(io_release_valid=1, io_release_bits_paddr=0x1801F)
    await e.step(fields)
    e.check("young cached load query accepted", e.pre[p + "ready"], 1)
    e.event("younger_load_allocation", uid=1, ROB=2, LQ=2, PA=0x18000, dataValid=data_valid,
        current_release=distance == 0, no_revoke=True, head_LQ=0)
    await e.step({p + "valid": 1, p + "bits_robIdx_value": 1, p + "bits_robIdx_isFormer": 1, p + "bits_paddr": 0x18000})
    e.check("older query accepted", e.pre[p + "ready"], 1)
    e.check("defined older-query response", e.post["io_query_0_resp_valid"], 1)
    actual = e.post["io_query_0_resp_bits_nuke"]
    e.event("older_load_violation_response", ROB=1, PA=0x18000, valid=1, nuke=actual)
    e.check("release association contract", actual, int(data_valid and distance in (0, 1)), fatal=False)
    await e.step({"io_ldWbPtr_value": 3})
    await e.idle(4, {"io_ldWbPtr_value": 3})
    e.finish()


@pytest.mark.parametrize("review_dut", ["load_queue_replay"], indirect=True)
@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("target", (0, 1))
@pytest.mark.parametrize("bitmap", (False, True))
async def test_invalid_feedback_must_not_relax_a_live_strict_owner(review_dut, lane, target, bitmap):
    e = review_dut
    e.metadata = dict(issue="LRQ-STRICT-001", lane=lane, target=target, bitmap=bitmap,
        domain="Replay input valid-only noninterference, one immutable normal LD; no private slot selection")
    uop = Uop(rob=RobPtr.encode(10), lq=QueuePtr.encode(20), sq=SqPtr.encode(8), offset=1,
        operation=6, strict=True, load_wait=True, store_set_hit=True, wait_sq=SqPtr.encode(7))
    req = Enqueue(True, uop, vaddr=0x10000, mask=255, aligned_type=3, need_replay=True,
        causes=1 << Cause.ADDRESS_DEPENDENCE, address_sq=SqPtr.encode(7))
    base = ReplayInputs(address_bits=(1 << 7) if bitmap else 0, upper=SqPtr.encode(64))

    async def cycle(**changes):
        await e.step(replay_encode(replace(base, **changes)))

    await cycle(enqueues=(req, Enqueue(), Enqueue()))
    e.check("new original strict Load allocated", e.post["io_replayAllocate"], 1)
    e.event("strict_owner_input", uid=1, ROB=10, LQ=20, SQ=8, dependency_SQ=7, strict=1,
        PA_low12=0, VA=0x10000, mask=255, opcode=6, lastBeat_PA5=0)
    for _ in range(4):
        await cycle()
    e.check("strict owner initially blocked", [e.post[f"io_replay_{i}_valid"] for i in range(3)], [0, 0, 0])
    dirty = replace(req, valid=False, replay_feedback=True, slot=target, need_replay=False, causes=0,
        uop=replace(req.uop, strict=False))
    await cycle(enqueues=tuple(dirty if i == lane else Enqueue() for i in range(3)))
    e.event("disabled_feedback_input", lane=lane, valid=0, schedIndex=target, isLoadReplay=1,
        no_address_wakeup=True, continuous_ready_pointer=0, address_ready_bit7=int(bitmap))
    early = []
    for _ in range(6):
        for bank in range(3):
            if e.post[f"io_replay_{bank}_valid"]:
                early.append(dict(tick=e.tick, bank=bank, slot=e.post[f"io_replay_{bank}_bits_replayQueueIdx"],
                    strict=e.post[f"io_replay_{bank}_bits_uop_loadWaitStrict"]))
        await cycle()
    e.event("strict_blocked_window_end", early_valid_observations=early,
        original_owner_still_allocated=e.post["io_replayAllocate"])
    e.check("disabled feedback has no scheduling side effect", early, [], fatal=False)
    base = replace(base, address_ready=SqPtr.encode(8))
    await cycle()
    e.event("legal_dependency_release", address_ready_pointer=8)
    for _ in range(30):
        if any(e.post[f"io_replay_{i}_valid"] for i in range(3)):
            break
        await cycle()
    banks = [i for i in range(3) if e.post[f"io_replay_{i}_valid"]]
    e.check("original Load available after legal release", len(banks), 1)
    bank = banks[0]
    slot = e.post[f"io_replay_{bank}_bits_replayQueueIdx"]
    e.check("public output owner identity", [e.post[f"io_replay_{bank}_bits_uop_robIdx_value"],
        e.post[f"io_replay_{bank}_bits_uop_loadWaitStrict"]], [10, 1])
    await cycle(ready=tuple(i == bank for i in range(3)))
    e.check("real original Replay grant", e.pre[f"io_replay_{bank}_valid"], 1)
    e.event("actual_Replay_grant_after_legal_release", uid=1, public_slot=slot, bank=bank)
    done = replace(req, replay_feedback=True, slot=slot, need_replay=False, causes=0)
    await cycle(enqueues=(done, Enqueue(), Enqueue()))
    e.event("same_public_slot_success_feedback", uid=1, slot=slot, need_rep=False)
    for _ in range(5):
        await cycle()
    e.check("original Replay owner actually freed", e.post["io_replayAllocate"], 0)
    e.finish()
