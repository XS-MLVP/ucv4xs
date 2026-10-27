from dataclasses import dataclass

from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import Redirect, RobPtr


def sq_number(ptr):
    if not 0 <= ptr.value < 64:
        raise ValueError("SQ physical value must be below 64")
    return int(ptr.first) * 128 + int(ptr.second) * 64 + ptr.value


@dataclass(frozen=True)
class Dispatch:
    valid: bool = False
    need_alloc: bool = False
    rob: RobPtr = RobPtr()
    flows: int = 0
    end: SqPtr = SqPtr()


@dataclass(frozen=True)
class Inputs:
    dispatch: tuple = (Dispatch(),) * 8
    rob_head: RobPtr = RobPtr()
    physical_deq: SqPtr = SqPtr()
    consumed: bool = False
    redirect: Redirect = Redirect()
    reset: bool = False


def encode(inp):
    if len(inp.dispatch) != 8:
        raise ValueError("actual VSQ has eight dispatch lanes")
    pins = {}
    def put(name, value, width):
        value = int(value)
        if not 0 <= value < 1 << width:
            raise ValueError(f"{name} outside {width} bits")
        pins[name] = value
    def rob(prefix, ptr):
        if not 0 <= ptr.value < 160:
            raise ValueError("actual ROB contains 160 entries")
        put(prefix + "flag", ptr.flag, 1)
        put(prefix + "value", ptr.value, 8)
        put(prefix + "isFormer", ptr.former, 1)
    def sq(prefix, ptr):
        sq_number(ptr)
        put(prefix + "first_flag", ptr.first, 1)
        put(prefix + "second_flag", ptr.second, 1)
        put(prefix + "value", ptr.value, 6)
    put("reset", inp.reset, 1)
    put("io_redirect_valid", inp.redirect.valid, 1)
    put("io_redirect_bits_level", inp.redirect.flush_self, 1)
    rob("io_redirect_bits_robIdx_", inp.redirect.rob)
    for lane, req in enumerate(inp.dispatch):
        prefix = f"io_enq_req_{lane}_"
        put(prefix + "valid", req.valid, 1)
        put(prefix + "bits_needAlloc", req.need_alloc, 1)
        rob(prefix + "bits_uop_robIdx_", req.rob)
        if not 0 <= req.flows <= 16:
            raise ValueError("current numLsElem producer domain is 0..16")
        put(prefix + "bits_uop_numLsElem", req.flows, 5)
        sq(prefix + "bits_reqEndPtr_sqIdx_", req.end)
    rob("io_fromRob_robHeadPtr_", inp.rob_head)
    sq("io_fromPhysicalQueue_deqPtr_", inp.physical_deq)
    put("io_fromPhysicalQueue_deqCount_valid", inp.consumed, 1)
    return pins
