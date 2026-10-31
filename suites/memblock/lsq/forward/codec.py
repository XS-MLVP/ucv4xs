"""All 695 optimized input pins; no binding to absent reset/perf/s1Resp."""
from .types import byte_count, sq_serial


def encode(inp):
    if (len(inp.queries), len(inp.translations), len(inp.stores), len(inp.second_pages)) != (3, 3, 64, 2):
        raise ValueError("real ForwardModule has 3 loads, 64 stores and 2 page records")
    values = {}
    def put(name, value, width):
        value = int(value)
        if not 0 <= value < 1 << width:
            raise ValueError(f"{name} is {width} bits")
        values[name] = value
    def ptr(prefix, value):
        sq_serial(value)
        put(prefix + "first_flag", value.first, 1)
        put(prefix + "second_flag", value.second, 1)
        put(prefix + "value", value.value, 6)
    for lane, query in enumerate(inp.queries):
        prefix = f"io_query_{lane}_"
        put(prefix + "s0Req_valid", query.valid, 1)
        put(prefix + "s0Req_bits_vaddr", query.vaddr, 50)
        put(prefix + "s0Req_bits_size", query.size, 3)
        put(prefix + "s0Req_bits_loadWaitBit", query.wait, 1)
        put(prefix + "s0Req_bits_loadWaitStrict", query.strict, 1)
        ptr(prefix + "s0Req_bits_sqIdx_", query.sq)
        ptr(prefix + "s0Req_bits_waitSqIdx_", query.wait_sq)
        put(prefix + "s1Req_paddr", inp.translations[lane].paddr, 48)
        put(prefix + "s1Kill", inp.translations[lane].kill, 1)
    for slot, store in enumerate(inp.stores):
        byte_count(store.size)
        data, ctrl = f"io_dataEntriesIn_{slot}_", f"io_ctrlEntriesIn_{slot}_"
        for suffix, field, width in (("size", "size", 3), ("vaddr", "vaddr", 50), ("paddrHigh", "page", 36),
                                     ("byteMask", "mask", 16), ("data", "data", 128), ("cboType", "cbo", 2)):
            put(data + suffix, getattr(store, field), width)
        for suffix, field in (("dataValid", "data_ready"), ("addrValid", "address_ready"), ("cross16Byte", "cross_word"), ("isCbo", "cache_operation")):
            put(ctrl + suffix, getattr(store, field), 1)
    for index, page in enumerate(inp.second_pages):
        put(f"io_unalignValidIn_{index}", page.valid, 1)
        put(f"io_unalignEntriesIn_{index}_paddr", page.paddr, 48)
        ptr(f"io_unalignEntriesIn_{index}_sqIdx_", page.sq)
    ptr("io_ctrlInfo_deqPtr_", inp.dequeue)
    ptr("io_ctrlInfo_physicalQueueUpper_", inp.upper)
    return values
