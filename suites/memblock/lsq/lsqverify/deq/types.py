from dataclasses import dataclass

from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import RobPtr


@dataclass(frozen=True)
class Store:
    vaddr: int = 0
    page: int = 0
    byte_mask: int = 0
    data: int = 0
    memory_type: int = 0
    cbo: int = 0
    hyper: bool = False
    data_valid: bool = False
    address_valid: bool = False
    inactive: bool = False
    cross_word: bool = False
    exception: bool = False
    committed: bool = False
    cache_operation: bool = False

    @property
    def paddr(self):
        return self.page * 4096 + self.vaddr % 4096


@dataclass(frozen=True)
class DeqControl:
    inactive: bool = False
    committed: bool = False
    finished: bool = False


@dataclass(frozen=True)
class SecondPage:
    valid: bool = False
    paddr: int = 0
    sq: SqPtr = SqPtr()


@dataclass(frozen=True)
class Inputs:
    stores: tuple = (Store(), Store())
    dequeue_controls: tuple = (DeqControl(), DeqControl())
    sbuffer_ready: tuple = (False, False)
    read_ptr: SqPtr = SqPtr()
    dequeue_ptrs: tuple = (SqPtr(), SqPtr.encode(1))
    rob: RobPtr = RobPtr()
    valid_count: int = 0
    uncache_ready: bool = False
    uncache_ack_valid: bool = False
    uncache_ack_to_load: bool = False
    uncache_response: bool = False
    cache_ready: bool = False
    cache_response: bool = False
    cache_denied: bool = False
    cache_corrupt: bool = False
    writeback_ready: bool = False
    sbuffer_empty: bool = True
    second_page: SecondPage = SecondPage()
    reset: bool = False


def encode(inp):
    if (len(inp.stores), len(inp.dequeue_controls), len(inp.sbuffer_ready), len(inp.dequeue_ptrs)) != (2, 2, 2, 2):
        raise ValueError("actual DeqModule has two read/dequeue/Sbuffer lanes")
    if not 0 <= inp.valid_count <= 128:
        raise ValueError("ordinary validCnt is virtual occupancy 0..128, not physical storage capacity")
    values = {}
    def put(name, value, width):
        value = int(value)
        if not 0 <= value < 1 << width:
            raise ValueError(f"{name} outside {width} bits")
        values[name] = value
    def sq(prefix, ptr):
        if not 0 <= ptr.value < 64:
            raise ValueError("physical SQ value outside 64 slots")
        put(prefix + "first_flag", ptr.first, 1)
        put(prefix + "second_flag", ptr.second, 1)
        put(prefix + "value", ptr.value, 6)
    for lane, store in enumerate(inp.stores):
        prefix = f"io_rdataDataEntries_{lane}_"
        for suffix, field, width in (("vaddr", "vaddr", 50), ("paddrHigh", "page", 36), ("byteMask", "byte_mask", 16),
                                     ("data", "data", 128), ("memoryType", "memory_type", 3), ("cboType", "cbo", 2)):
            put(prefix + suffix, getattr(store, field), width)
        if lane == 0:
            put(prefix + "isHyper", store.hyper, 1)
        prefix = f"io_rdataCtrlEntries_{lane}_"
        fields = (("vecInactive", "inactive"), ("cross16Byte", "cross_word"), ("committed", "committed"), ("isCbo", "cache_operation"))
        if lane == 0:
            fields += (("dataValid", "data_valid"), ("addrValid", "address_valid"), ("hasException", "exception"))
        for suffix, field in fields:
            put(prefix + suffix, getattr(store, field), 1)
    for lane, ctrl in enumerate(inp.dequeue_controls):
        for suffix, field in (("vecInactive", "inactive"), ("committed", "committed"), ("handleFinish", "finished")):
            put(f"io_deqCtrlEntries_{lane}_{suffix}", getattr(ctrl, field), 1)
    for name, field in (("io_toUncacheBuffer_req_ready", "uncache_ready"), ("io_toUncacheBuffer_idResp_valid", "uncache_ack_valid"),
                        ("io_toUncacheBuffer_idResp_bits_is2lq", "uncache_ack_to_load"), ("io_toUncacheBuffer_resp_valid", "uncache_response"),
                        ("io_toDCache_req_ready", "cache_ready"), ("io_toDCache_resp_valid", "cache_response"),
                        ("io_toDCache_resp_bits_denied", "cache_denied"), ("io_toDCache_resp_bits_corrupt", "cache_corrupt"),
                        ("io_writeBack_ready", "writeback_ready"), ("io_sbufferCtrl_resp_empty", "sbuffer_empty"), ("reset", "reset")):
        put(name, getattr(inp, field), 1)
    for lane, ready in enumerate(inp.sbuffer_ready):
        put(f"io_writeToSbuffer_req_{lane}_ready", ready, 1)
    sq("io_rdataPtrExt_0_", inp.read_ptr)
    for lane, ptr in enumerate(inp.dequeue_ptrs):
        sq(f"io_deqPtrExt_{lane}_", ptr)
    put("io_validCnt", inp.valid_count, 8)
    if not 0 <= inp.rob.value < 160:
        raise ValueError("ROB value outside 160 entries")
    for suffix, field, width in (("flag", "flag", 1), ("value", "value", 8), ("isFormer", "former", 1)):
        put("io_fromVirtualStoreQueue_headRobIdx_" + suffix, getattr(inp.rob, field), width)
    put("io_fromUnalignQueue_valid", inp.second_page.valid, 1)
    put("io_fromUnalignQueue_bits_paddr", inp.second_page.paddr, 48)
    sq("io_fromUnalignQueue_bits_sqIdx_", inp.second_page.sq)
    return values
