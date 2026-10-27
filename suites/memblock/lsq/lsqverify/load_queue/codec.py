"""Exact retained pins; no writable stand-ins for the four internal feedbacks."""
from dataclasses import replace
from functools import lru_cache
import re

from lsqverify.native import ROOT
from lsqverify.replay.codec import encode as replay_encode, lq, rob, sq
from lsqverify.replay.types import Inputs as ReplayInputs, SOURCE_EXCEPTION_BITS
from .types import EXCEPTION_BITS


@lru_cache(maxsize=1)
def ports():
    text = (ROOT / "rtl/load_queue/LoadQueue.sv").read_text().split(");", 1)[0]
    result = {direction: {} for direction in ("input", "output")}
    for direction, high, low, name in re.findall(r"\b(input|output)\s+(?:\[(\d+):(\d+)\]\s+)?(\w+)", text):
        if name != "clock":
            result[direction][name] = int(high) - int(low) + 1 if high else 1
    assert len(result["input"]) == 622 and len(result["output"]) == 266
    return result


def replay_inputs(inp):
    return ReplayInputs(enqueues=tuple(replace(load.execution, uop=replace(load.execution.uop,
                         exceptions=load.exceptions & sum(1 << bit for bit in SOURCE_EXCEPTION_BITS))) for load in inp.loads),
                        ready=inp.replay_ready, address_wakeups=inp.address_wakeups, data_wakeups=inp.data_wakeups,
                        data_writes=inp.data_writes, refills=inp.refills, l2_hints=inp.l2_hints,
                        slow_tlb=inp.slow_tlb, fast_tlb=inp.fast_tlb, address_ready=inp.address_ready,
                        address_bits=inp.address_bits, data_ready=inp.data_ready, data_bits=inp.data_bits,
                        dequeue=inp.dequeue, upper=inp.upper, sq_empty=inp.sq_empty, head=inp.pending_next,
                        redirect=inp.redirect, reset=inp.reset)


def encode(inp):
    shapes = (len(inp.dispatch), len(inp.loads), len(inp.rar_queries), len(inp.raw_queries), len(inp.stores),
              len(inp.rar_revoke_last), len(inp.rar_revoke_older), len(inp.raw_revoke_last), len(inp.raw_revoke_older), len(inp.bypass))
    if shapes != (8, 3, 3, 3, 2, 3, 3, 3, 3, 3):
        raise ValueError("LoadQueue requires exact actual 8/3/2-lane shapes")
    values = {}
    def put(prefix, fields):
        values.update({prefix + suffix: int(value) for suffix, value in fields.items()})
    source = replay_encode(replay_inputs(inp))
    for key, value in source.items():
        if key.startswith("io_enq_"):
            values[key.replace("io_enq_", "io_ldu_ldin_", 1)] = value
        elif key.startswith(("io_stAddrReady", "io_stDataReady", "io_sqDeqPtr_", "io_physicalUpperSqIdx_")):
            values[key.replace("io_", "io_sq_", 1)] = value
        elif key == "io_sqEmpty":
            values["io_sq_sqEmpty"] = value
        elif key.startswith("io_robHeadPtr_"):
            values[key.replace("io_robHeadPtr_", "io_rob_pendingPtrNext_", 1)] = value
        elif key.startswith(("io_storeAddrWakeup_", "io_storeDataWakeup_")):
            name, lane, suffix = key.removeprefix("io_").split("_", 2)
            values[f"io_wakeupToLRQ_{int(lane) + (2 if name == 'storeDataWakeup' else 0)}_{suffix}"] = value
        elif key.startswith("io_storeDataWrite_"):
            name = key.replace("io_storeDataWrite_", "io_std_storeDataIn_", 1)
            if "_bits_" in name:
                name = name.replace("_bits_", "_bits_sqIdx_", 1)
            values[name] = value
        elif key.startswith(("io_rarFull", "io_rawFull", "io_ldWbPtr_", "io_mmioWakeup_", "io_ncWakeup_")):
            continue
        else:
            values[key] = value
    for lane, load in enumerate(inp.loads):
        prefix = f"io_ldu_ldin_{lane}_bits_"
        if load.exceptions & ~sum(1 << bit for bit in EXCEPTION_BITS):
            raise ValueError("exception bit deleted from this actual top")
        put(prefix, dict(fullva=load.fullva, paddr=load.paddr, gpaddr=load.gpaddr, mmio=load.mmio,
                         memBackTypeMM=load.memory_backed, isHyper=load.hyper, isForVSnonLeafPTE=load.nonleaf,
                         updateAddrValid=load.update_address))
        for bit in EXCEPTION_BITS:
            values[prefix + f"uop_exceptionVec_{bit}"] = load.exceptions >> bit & 1
    for lane, dispatch in enumerate(inp.dispatch):
        if not 0 <= dispatch.flows <= 16:
            raise ValueError("dispatch flow count outside 0..16")
        prefix = f"io_enq_req_{lane}_"
        put(prefix, dict(valid=dispatch.valid, bits_numLsElem=dispatch.flows))
        put(prefix + "bits_robIdx_", rob(dispatch.rob))
        put(prefix + "bits_lqIdx_", lq(dispatch.start))
    for family, queries, one, two in (("rar", inp.rar_queries, inp.rar_revoke_last, inp.rar_revoke_older),
                                       ("raw", inp.raw_queries, inp.raw_revoke_last, inp.raw_revoke_older)):
        for lane, query in enumerate(queries):
            prefix = f"io_ldu_{family}NukeQuery_{lane}_"
            put(prefix, dict(req_valid=query.valid, req_bits_paddr=query.paddr, req_bits_dataValid=query.data_valid,
                             revokeLastCycle=one[lane], revokeLastLastCycle=two[lane]))
            put(prefix + "req_bits_robIdx_", rob(query.rob))
            if family == "rar":
                put(prefix + "req_bits_lqIdx_", lq(query.lq))
                values[prefix + "req_bits_nc"] = int(query.nc)
            else:
                put(prefix + "req_bits_sqIdx_", sq(query.sq))
                put(prefix, dict(req_bits_mask=query.mask, req_bits_isRVC=query.is_rvc, req_bits_ftqPtr_flag=query.ftq.flag,
                                 req_bits_ftqPtr_value=query.ftq.value, req_bits_ftqOffset=query.ftq_offset,
                                 req_bits_debugInfo_runahead_checkpoint_id=query.checkpoint))
    for lane, store in enumerate(inp.stores):
        prefix = f"io_sta_storeAddrIn_{lane}_"
        put(prefix, dict(valid=store.valid, bits_paddr=store.paddr, bits_mask=store.mask, bits_wlineflag=store.wline,
                         bits_tlbMiss=store.tlb_miss, bits_uop_ftqPtr_flag=store.ftq_flag, bits_uop_ftqPtr_value=store.ftq_value,
                         bits_uop_ftqOffset=store.ftq_offset, bits_uop_isRVC=store.is_rvc))
        put(prefix + "bits_uop_robIdx_", rob(store.rob))
    for lane, bypass in enumerate(inp.bypass):
        prefix = f"io_bypass_{lane}_s0Req_"
        put(prefix, dict(valid=bypass.valid, bits_isNCReplay=bypass.nc, bits_isMMIOReplay=bypass.mmio))
        put(prefix + "bits_lqIdx_", lq(bypass.lq))
    put("io_rob_pendingPtr_", rob(inp.pending))
    put("io_release_", dict(valid=inp.release.valid, bits_paddr=inp.release.paddr))
    bus = inp.bus
    put("io_uncache_", dict(req_ready=bus.ready, idResp_valid=bus.ack, idResp_bits_mid=bus.mid, idResp_bits_sid=bus.sid,
                            resp_valid=bus.response, resp_bits_data=bus.data, resp_bits_id=bus.response_id,
                            resp_bits_error=bus.error, resp_bits_nderr=bus.nderr))
    widths = ports()["input"]
    assert set(values) == set(widths), ("missing", set(widths) - set(values), "extra", set(values) - set(widths))
    for name, width in widths.items():
        if not 0 <= values[name] < 1 << width:
            raise ValueError(f"{name} outside retained {width}-bit port")
    return values
