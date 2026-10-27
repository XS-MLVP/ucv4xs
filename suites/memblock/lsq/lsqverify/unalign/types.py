from dataclasses import dataclass

from lsqverify.raw.types import SqPtr


@dataclass(frozen=True)
class Request:
    valid: bool = False
    sq: SqPtr = SqPtr()
    paddr: int = 0


@dataclass(frozen=True)
class Recovery:
    valid: bool = False
    sq: SqPtr = SqPtr()


@dataclass(frozen=True)
class Inputs:
    requests: tuple[Request, ...] = (Request(),) * 2
    address_ready: SqPtr = SqPtr()
    ready: bool = False
    redirect: Recovery = Recovery()
    reset: bool = False


def serial(ptr):
    if not 0 <= ptr.value < 64:
        raise ValueError("SQ physical value must be below 64")
    return int(ptr.first) * 128 + int(ptr.second) * 64 + ptr.value


def distance(left, right):
    delta = (serial(left) - serial(right)) % 256
    if delta == 128:
        raise ValueError("SQ half-ring age is ambiguous")
    return delta


def canceled(ptr, redirect):
    return redirect.valid and distance(ptr, redirect.sq) < 128


def encode(inp):
    if len(inp.requests) != 2:
        raise ValueError("two STA input lanes are required")
    result = {"reset": int(inp.reset), "io_redirect_valid": int(inp.redirect.valid), "io_toDeqModule_ready": int(inp.ready)}
    def pointer(prefix, ptr):
        serial(ptr)
        result.update({prefix + "first_flag": int(ptr.first), prefix + "second_flag": int(ptr.second), prefix + "value": ptr.value})
    pointer("io_redirect_bits_", inp.redirect.sq)
    pointer("io_fromSQ_addrReadyPtr_", inp.address_ready)
    for lane, req in enumerate(inp.requests):
        if not 0 <= req.paddr < 1 << 48:
            raise ValueError("second physical page input is 48 bits")
        prefix = f"io_fromStaS1_{lane}_"
        result[prefix + "valid"] = int(req.valid)
        result[prefix + "bits_paddr"] = req.paddr
        pointer(prefix + "bits_sqIdx_", req.sq)
    return result
