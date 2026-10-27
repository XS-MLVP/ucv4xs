"""Committed write requests and consumption credits, not physical registers."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Write:
    paddr: int = 0
    vaddr: int = 0
    data: int = 0
    mask: int = 0
    wline: bool = False
    credit: bool = True


@dataclass(frozen=True)
class Offer:
    valid: bool = False
    write: Write = Write()


@dataclass(frozen=True)
class Inputs:
    offers: tuple[Offer, ...] = (Offer(),) * 2
    ready: tuple[bool, ...] = (False,) * 2
    reset: bool = False


def encode(inp):
    if len(inp.offers) != 2 or len(inp.ready) != 2:
        raise ValueError("native queue has two input and output lanes")
    if inp.offers[1].valid and not inp.offers[0].valid:
        raise ValueError("DeqModule produces a valid prefix")
    if inp.ready[1] and not inp.ready[0]:
        raise ValueError("real Sbuffer ready is a prefix")
    if not inp.offers[1].write.credit:
        raise ValueError("input lane1 credit is compiled constant true")
    result = {"reset": int(inp.reset)}
    for lane, offer in enumerate(inp.offers):
        prefix = f"io_fromDeqModule_{lane}_"
        result[prefix + "valid"] = int(offer.valid)
        for name, field, width in (("addr", "paddr", 48), ("vaddr", "vaddr", 50), ("data", "data", 128), ("mask", "mask", 16), ("wline", "wline", 1)):
            value = int(getattr(offer.write, field))
            if not 0 <= value < 1 << width:
                raise ValueError(f"{field} outside public width")
            result[prefix + "bits_" + name] = value
        if lane == 0:
            result[prefix + "bits_deqPtrMove"] = int(offer.write.credit)
        result[f"io_toSbuffer_req_{lane}_ready"] = int(inp.ready[lane])
    return result
