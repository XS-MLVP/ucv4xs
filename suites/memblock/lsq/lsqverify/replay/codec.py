"""Pure transaction-to-public-pin encoding with explicit legal-domain checks.

This is an adapter, not a correctness reference. Its existence is not native
DUT validation; tests/monitor/checker and coverage iteration are still required.
"""
from .types import SOURCE_EXCEPTION_BITS


def rob(ptr):
    if not 0 <= ptr.value < 160:
        raise ValueError("ROB slot outside 160 entries")
    return {"flag": ptr.flag, "value": ptr.value, "isFormer": ptr.former}


def sq(ptr):
    if not 0 <= ptr.value < 64:
        raise ValueError("SQ physical index outside 64 entries")
    return {"first_flag": ptr.first, "second_flag": ptr.second, "value": ptr.value}


def lq(ptr):
    if not 0 <= ptr.value < 120:
        raise ValueError("LQ index outside 120 entries")
    return {"flag": ptr.flag, "value": ptr.value}


def encode(inp):
    sizes = (len(inp.enqueues), len(inp.ready), len(inp.address_wakeups), len(inp.data_wakeups),
             len(inp.data_writes), len(inp.refills), len(inp.l2_hints))
    if sizes != (3, 3, 2, 2, 2, 2, 2):
        raise ValueError("Replay adapter needs exact 3-lane/2-channel configuration")
    if not 0 <= inp.address_bits < 1 << 64 or not 0 <= inp.data_bits < 1 << 64:
        raise ValueError("SQ readiness vectors exceed 64 actual pins")
    values = {"reset": inp.reset, "io_redirect_valid": inp.redirect.valid, "io_redirect_bits_level": inp.redirect.flush_self,
              "io_sqEmpty": inp.sq_empty, "io_rarFull": inp.rar_full, "io_rawFull": inp.raw_full}
    def put(prefix, fields):
        values.update({prefix + key: int(value) for key, value in fields.items()})
    put("io_redirect_bits_robIdx_", rob(inp.redirect.rob))
    put("io_robHeadPtr_", rob(inp.head))
    put("io_ldWbPtr_", lq(inp.writeback))
    for name, ptr in (("stAddrReadySqPtr", inp.address_ready), ("stDataReadySqPtr", inp.data_ready), ("sqDeqPtr", inp.dequeue), ("physicalUpperSqIdx", inp.upper)):
        put("io_" + name + "_", sq(ptr))
    for bit in range(64):
        values[f"io_stAddrReadyVec_{bit}"] = inp.address_bits >> bit & 1
        values[f"io_stDataReadyVec_{bit}"] = inp.data_bits >> bit & 1
    for name, wake in (("mmio", inp.mmio), ("nc", inp.nc)):
        values[f"io_{name}Wakeup_valid"] = wake.valid
        put(f"io_{name}Wakeup_bits_", lq(wake.lq))
    for lane in range(2):
        for name, wakes, suffix in (("storeAddrWakeup", inp.address_wakeups, "sqIdx_"),
                                    ("storeDataWakeup", inp.data_wakeups, "sqIdx_"), ("storeDataWrite", inp.data_writes, "")):
            values[f"io_{name}_{lane}_valid"] = wakes[lane].valid
            put(f"io_{name}_{lane}_bits_" + suffix, sq(wakes[lane].sq))
        if not 0 <= inp.refills[lane].mshr < 16 or not 0 <= inp.l2_hints[lane].mshr < 16:
            raise ValueError("MSHR identity exceeds retained 4-bit pins")
        values[f"io_loadWakeup_{lane}_valid"] = inp.refills[lane].valid
        values[f"io_loadWakeup_{lane}_bits_mshrId"] = inp.refills[lane].mshr
        values[f"io_l2_hint_{lane}_valid"] = inp.l2_hints[lane].valid
        values[f"io_l2_hint_{lane}_bits_sourceId"] = inp.l2_hints[lane].mshr
        values[f"io_l2_hint_{lane}_bits_isKeyword"] = inp.l2_hints[lane].keyword
    if inp.fast_tlb.replay_all:
        raise ValueError("fast TLB hint has no replay_all pin")
    for name, hint in (("tlb_hint_resp", inp.slow_tlb), ("fast_tlb_hint", inp.fast_tlb)):
        if not 0 <= hint.identity < 16:
            raise ValueError("TLB identity exceeds retained 4-bit pins")
        values[f"io_{name}_valid"] = hint.valid
        values[f"io_{name}_bits_id"] = hint.identity
    values["io_tlb_hint_resp_bits_replay_all"] = inp.slow_tlb.replay_all
    for lane, req in enumerate(inp.enqueues):
        uop = req.uop
        if not (0 <= req.vaddr < 1 << 50 and 0 <= req.mask < 1 << 16 and 0 <= req.aligned_type < 8
                and 0 <= req.slot < 128 and 0 <= req.mshr < 16 and 0 <= req.tlb_id < 16 and 0 <= req.causes < 1 << 13
                and 0 <= uop.ftq.value < 64 and 0 <= uop.offset < 32 and 0 <= uop.checkpoint < 1 << 64
                and 0 <= uop.operation < 1 << 12 and 0 <= uop.destination < 256):
            raise ValueError("Replay metadata exceeds actual public pins")
        if uop.exceptions & ~sum(1 << bit for bit in SOURCE_EXCEPTION_BITS):
            raise ValueError("source exception bit deleted from current Replay top")
        if req.valid and req.replay_feedback and req.slot >= 120:
            raise ValueError("feedback may not target the unused 120..127 encoding")
        if req.valid and req.need_replay and (req.causes.bit_count() != 1 or req.causes == 1 << 12):
            raise ValueError("ordinary replay traffic requires one supported cause; reserved/multi/zero cause is domain-external")
        prefix = f"io_enq_{lane}_"
        fields = {"valid": req.valid, "bits_uop_isRVC": uop.rvc, "bits_uop_ftqPtr_flag": uop.ftq.flag,
                  "bits_uop_ftqPtr_value": uop.ftq.value, "bits_uop_ftqOffset": uop.offset, "bits_uop_fuOpType": uop.operation,
                  "bits_uop_rfWen": uop.integer_write, "bits_uop_fpWen": uop.fp_write, "bits_uop_vecWen": uop.vector_write,
                  "bits_uop_v0Wen": uop.v0_write, "bits_uop_pdest": uop.destination,
                  "bits_uop_perfDebugInfo_runahead_checkpoint_id": uop.checkpoint,
                  "bits_uop_storeSetHit": uop.store_set_hit, "bits_uop_loadWaitBit": uop.load_wait, "bits_uop_loadWaitStrict": uop.strict,
                  "bits_vaddr": req.vaddr, "bits_mask": req.mask, "bits_nc": req.nc,
                  "bits_specialModeEligible": req.special_eligible, "bits_specialModeRequest": req.special_request,
                  "bits_isvec": req.vector, "bits_alignedType": req.aligned_type, "bits_isLoadReplay": req.replay_feedback,
                  "bits_handledByMSHR": req.handled, "bits_schedIndex": req.slot, "bits_rep_info_mshr_id": req.mshr,
                  "bits_rep_info_last_beat": req.last_beat, "bits_rep_info_need_rep": req.need_replay,
                  "bits_rep_info_tlb_id": req.tlb_id, "bits_rep_info_tlb_full": req.tlb_full,
                  "bits_rep_info_rep_from_unalign_head": req.unaligned_head}
        fields.update({f"bits_uop_exceptionVec_{bit}": uop.exceptions >> bit & 1 for bit in SOURCE_EXCEPTION_BITS})
        fields.update({f"bits_rep_info_cause_{bit}": req.causes >> bit & 1 for bit in range(13)})
        put(prefix, fields)
        put(prefix + "bits_uop_robIdx_", rob(uop.rob))
        put(prefix + "bits_uop_lqIdx_", lq(uop.lq))
        put(prefix + "bits_uop_sqIdx_", sq(uop.sq))
        put(prefix + "bits_uop_waitSqIdx_", sq(uop.wait_sq))
        put(prefix + "bits_rep_info_data_inv_sq_idx_", sq(req.data_sq))
        put(prefix + "bits_rep_info_addr_inv_sq_idx_", sq(req.address_sq))
        values[f"io_replay_{lane}_ready"] = inp.ready[lane]
    return {name: int(value) for name, value in values.items()}
