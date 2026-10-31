"""Pure adapters; shared-field collisions must agree and every real pin is bound.

Child codec reuse is not a replacement for real RTL or a functional oracle.
The child-only internal feedback placeholders never appear in wrapper Inputs
or the result; a future semantic connection must supply OLD inferred feedback.
"""
from dataclasses import fields
from functools import lru_cache
import re

from suites.memblock.lsq.native import ROOT
from suites.memblock.lsq.load_queue.codec import encode as load_encode
from suites.memblock.lsq.load_queue.types import Bus as LoadBus, Inputs as LoadInputs
from suites.memblock.lsq.psq.types import Data as PhysicalData
from suites.memblock.lsq.raw.types import Store
from suites.memblock.lsq.replay.codec import lq, rob, sq
from suites.memblock.lsq.replay.types import StoreWakeup
from suites.memblock.lsq.store_queue.types import Inputs as StoreInputs, encode as store_encode


@lru_cache(maxsize=1)
def ports():
    text = (ROOT / "rtl/lsq_wrapper/LsqWrapper.sv").read_text().split(");", 1)[0]
    result = {direction: {} for direction in ("input", "output")}
    for direction, high, low, name in re.findall(r"\b(input|output)\s+(?:\[(\d+):(\d+)\]\s+)?(\w+)", text):
        if name != "clock":
            result[direction][name] = int(high) - int(low) + 1 if high else 1
    assert len(result["input"]) == 603 and len(result["output"]) == 458
    return result


def load_public_view(inp):
    names = ("loads", "rar_queries", "raw_queries", "rar_revoke_last", "rar_revoke_older", "raw_revoke_last", "raw_revoke_older",
             "replay_ready", "address_wakeups", "data_wakeups", "refills", "l2_hints", "slow_tlb", "fast_tlb", "pending", "pending_next",
             "release", "bypass", "redirect", "reset")
    return LoadInputs(**{name: getattr(inp, name) for name in names},
                      stores=tuple(Store(a.valid, a.rob, a.paddr, a.mask, a.wline, a.tlb_miss, a.ftq.flag,
                                         a.ftq.value, a.ftq_offset, a.rvc) for a in inp.addresses),
                      data_writes=tuple(StoreWakeup(d.valid, d.sq) for d in inp.data),
                      bus=LoadBus(**{field.name: getattr(inp.bus, field.name) for field in fields(LoadBus)}))


def store_public_view(inp):
    names = ("addresses", "attributes", "second_pages", "queries", "translations", "sbuffer_ready", "sbuffer_empty", "cache_ready",
             "cache_response", "cache_denied", "cache_corrupt", "writeback_ready", "redirect", "reset")
    return StoreInputs(**{name: getattr(inp, name) for name in names}, rob_head=inp.pending,
                       data=tuple(PhysicalData(d.valid, d.sq.value, d.fu_op, d.data) for d in inp.data))


def encode(inp):
    sizes = {"dispatch": 8, "loads": 3, "rar_queries": 3, "raw_queries": 3, "rar_revoke_last": 3, "rar_revoke_older": 3,
             "raw_revoke_last": 3, "raw_revoke_older": 3, "replay_ready": 3, "bypass": 3, "addresses": 2, "attributes": 2,
             "data": 2, "second_pages": 2, "queries": 3, "translations": 3, "address_wakeups": 2, "data_wakeups": 2,
             "refills": 2, "l2_hints": 2, "sbuffer_ready": 2}
    if any(len(getattr(inp, name)) != size for name, size in sizes.items()):
        raise ValueError("wrapper requires exact retained 8/3/2-lane shapes")
    widths, values = ports()["input"], {}
    def put(name, value):
        value = int(value)
        assert name in widths, ("not a retained wrapper input", name)
        if name in values:
            assert values[name] == value, ("inconsistent shared public field", name, values[name], value)
        values[name] = value
    for key, value in load_encode(load_public_view(inp)).items():
        if key.startswith(("io_enq_", "io_sq_")):
            continue
        name = key.replace("io_redirect_", "io_brqRedirect_", 1)
        put(name, value)
    for key, value in store_encode(store_public_view(inp)).items():
        if key.startswith(("io_enq_", "io_toUncacheBuffer_")):
            continue
        name = key
        for old, new in (("io_fromStoreUnit_", "io_sta_"), ("io_storeDataIn_", "io_std_storeDataIn_"),
                         ("io_writeToSbuffer_", "io_sbuffer_"), ("io_fromRob_robHeadPtr_", "io_rob_pendingPtr_"),
                         ("io_redirect_", "io_brqRedirect_"), ("io_toDCache_req_", "io_cmoOpReq_"),
                         ("io_toDCache_resp_", "io_cmoOpResp_"), ("io_writeBack_", "io_mmioStout_"),
                         ("io_sbufferCtrl_resp_", "io_flushSbuffer_")):
            if name.startswith(old):
                name = new + name[len(old):]
                break
        put(name, value)
    for lane, request in enumerate(inp.dispatch):
        if not 0 <= request.need_alloc <= 3 or not 0 <= request.flows <= 16:
            raise ValueError("wrapper dispatch mask/flow outside retained domain")
        p = f"io_enq_req_{lane}_"
        put(f"io_enq_needAlloc_{lane}", request.need_alloc)
        put(p + "valid", request.valid)
        put(p + "bits_uop_numLsElem", request.flows)
        for suffix, value in rob(request.rob).items():
            put(p + "bits_uop_robIdx_" + suffix, value)
        for suffix, value in lq(request.load_start).items():
            put(p + "bits_reqStartPtr_lqIdx_" + suffix, value)
        for suffix, value in sq(request.store_end).items():
            put(p + "bits_reqEndPtr_sqIdx_" + suffix, value)
    put("io_uncacheOutstanding", inp.bus.outstanding)
    put("io_uncache_idResp_bits_is2lq", inp.bus.ack_to_load)
    put("io_uncache_resp_bits_is2lq", inp.bus.response_to_load)
    assert set(values) == set(widths), ("missing wrapper inputs", set(widths) - set(values))
    for name, width in widths.items():
        if not 0 <= values[name] < 1 << width:
            raise ValueError(f"{name} outside actual {width}-bit port")
    return values
