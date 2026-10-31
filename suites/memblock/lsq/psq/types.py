from dataclasses import dataclass

from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import RobPtr


@dataclass(frozen=True)
class Address:
    valid: bool = False
    slot: int = 0
    fu_op: int = 0
    vaddr: int = 0
    paddr: int = 0
    size: int = 0
    tlb_miss: bool = False
    hyper: bool = False
    unaligned: bool = False
    cross_word: bool = False
    last: bool = True


@dataclass(frozen=True)
class Attributes:
    nc: bool = False
    mmio: bool = False
    memory: bool = True
    exception: bool = False
    last: bool = True


@dataclass(frozen=True)
class Data:
    valid: bool = False
    slot: int = 0
    fu_op: int = 0
    data: int = 0


@dataclass(frozen=True)
class SecondPage:
    valid: bool = False
    sq: SqPtr = SqPtr()
    paddr: int = 0


@dataclass(frozen=True)
class Inputs:
    addresses: tuple = (Address(), Address())
    attributes: tuple = (Attributes(), Attributes())
    data: tuple = (Data(), Data())
    second_pages: tuple = (SecondPage(), SecondPage())
    queries: tuple = (Query(),) * 3
    translations: tuple = (Translation(),) * 3
    enqueue: SqPtr = SqPtr()
    retired: SqPtr = SqPtr()
    precommit_valid: bool = False
    precommit: SqPtr = SqPtr()
    redirect_valid: bool = False
    redirect: SqPtr = SqPtr()
    rob: RobPtr = RobPtr()
    sbuffer_ready: tuple = (False, False)
    sbuffer_empty: bool = True
    cache_ready: bool = False
    cache_response: bool = False
    cache_denied: bool = False
    cache_corrupt: bool = False
    uncache_ready: bool = False
    uncache_ack_valid: bool = False
    uncache_ack_to_load: bool = False
    uncache_response: bool = False
    writeback_ready: bool = False
    reset: bool = False


def encode(inp):
    values = {}
    for name in ("addresses", "attributes", "data", "second_pages", "sbuffer_ready"):
        if len(getattr(inp, name)) != 2:
            raise ValueError("actual PSQ has two " + name + " lanes")
    if len(inp.queries) != 3 or len(inp.translations) != 3:
        raise ValueError("actual PSQ has three forward lanes")
    def put(name, value, width=1):
        value = int(value)
        if not 0 <= value < 1 << width:
            raise ValueError(name + " outside retained public width")
        values[name] = value
    def sq(prefix, ptr):
        put(prefix + "first_flag", ptr.first)
        put(prefix + "second_flag", ptr.second)
        put(prefix + "value", ptr.value, 6)
    for lane in range(2):
        address, data, attr, page = inp.addresses[lane], inp.data[lane], inp.attributes[lane], inp.second_pages[lane]
        prefix = f"io_fromStoreUnit_storeAddrIn_{lane}_"
        put(prefix + "valid", address.valid)
        put(prefix + "bits_uop_sqIdx_value", address.slot, 6)
        put(prefix + "bits_uop_fuOpType", address.fu_op, 12)
        for suffix, field, width in (("tlbMiss", "tlb_miss", 1), ("vaddr", "vaddr", 50), ("paddr", "paddr", 48), ("size", "size", 3),
                                     ("isHyper", "hyper", 1), ("isUnalign", "unaligned", 1), ("cross16Byte", "cross_word", 1), ("isLastRequest", "last", 1)):
            put(prefix + "bits_" + suffix, getattr(address, field), width)
        prefix = f"io_fromStoreUnit_storeAddrInRe_{lane}_"
        for suffix, field in (("nc", "nc"), ("mmio", "mmio"), ("memBackTypeMM", "memory"), ("hasException", "exception"), ("isLastRequest", "last")):
            put(prefix + suffix, getattr(attr, field))
        prefix = f"io_storeDataIn_{lane}_"
        put(prefix + "valid", data.valid)
        put(prefix + "bits_fuOpType", data.fu_op, 12)
        put(prefix + "bits_data", data.data, 128)
        put(prefix + "bits_sqIdx_value", data.slot, 6)
        prefix = f"io_fromStoreUnit_unalignQueueReq_{lane}_"
        put(prefix + "valid", page.valid)
        put(prefix + "bits_paddr", page.paddr, 48)
        sq(prefix + "bits_sqIdx_", page.sq)
        put(f"io_writeToSbuffer_req_{lane}_ready", inp.sbuffer_ready[lane])
    for lane, (query, translation) in enumerate(zip(inp.queries, inp.translations)):
        prefix = f"io_forward_{lane}_"
        put(prefix + "s0Req_valid", query.valid)
        put(prefix + "s0Req_bits_vaddr", query.vaddr, 50)
        put(prefix + "s0Req_bits_size", query.size, 3)
        put(prefix + "s0Req_bits_loadWaitBit", query.wait)
        put(prefix + "s0Req_bits_loadWaitStrict", query.strict)
        sq(prefix + "s0Req_bits_sqIdx_", query.sq)
        sq(prefix + "s0Req_bits_waitSqIdx_", query.wait_sq)
        put(prefix + "s1Req_paddr", translation.paddr, 48)
        put(prefix + "s1Kill", translation.kill)
    for suffix, ptr in (("physicalQueueEnqPtr", inp.enqueue), ("retiredPtr", inp.retired), ("preCommitPtr_bits", inp.precommit), ("redirectPtr_bits", inp.redirect)):
        sq("io_fromVirtualStoreQueue_" + suffix + "_", ptr)
    put("io_fromVirtualStoreQueue_preCommitPtr_valid", inp.precommit_valid)
    put("io_fromVirtualStoreQueue_redirectPtr_valid", inp.redirect_valid)
    if not 0 <= inp.rob.value < 160:
        raise ValueError("ROB slot outside 160 entries")
    for suffix, field, width in (("flag", "flag", 1), ("value", "value", 8), ("isFormer", "former", 1)):
        put("io_fromVirtualStoreQueue_headRobIdx_" + suffix, getattr(inp.rob, field), width)
    for port, field in (("reset", "reset"), ("io_sbufferCtrl_resp_empty", "sbuffer_empty"), ("io_toDCache_req_ready", "cache_ready"),
                        ("io_toDCache_resp_valid", "cache_response"), ("io_toDCache_resp_bits_denied", "cache_denied"), ("io_toDCache_resp_bits_corrupt", "cache_corrupt"),
                        ("io_toUncacheBuffer_req_ready", "uncache_ready"), ("io_toUncacheBuffer_idResp_valid", "uncache_ack_valid"),
                        ("io_toUncacheBuffer_idResp_bits_is2lq", "uncache_ack_to_load"), ("io_toUncacheBuffer_resp_valid", "uncache_response"), ("io_writeBack_ready", "writeback_ready")):
        put(port, getattr(inp, field))
    return values
