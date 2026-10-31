"""Functional reference model for ICacheMainPipe.

The model is written from the interface contract and the documented fetch
semantics, not from the RTL body:

* A fetch request carries up to two cache lines (the FTQ guarantees at most one
  line crossing per request) with the virtual set index of each line. The
  way-lookup entry supplies, per line, the waymask of a possible hit; one
  physical page tag is shared by both lines of a fetch.
* A line is fetched from the data array when its waymask is non-zero; a line
  with an empty waymask is a miss and must be requested from the miss unit
  exactly once. The pipeline holds the request until every line is a hit or is
  known to be unfetchable, then presents one response to the IFU.
* A miss response supplies the refilled line for one set/block. After it the
  line counts as a hit and its data replaces the array data for that line. A
  corrupt/denied refill raises hardware-error/access-fault for the request
  instead of silently returning data.
* ITLB/PMP exceptions and back-end exceptions suppress the data fetch; an
  exception is reported to the IFU instead of a miss request. ``pmp.mmio`` and
  uncacheable PBMT memory types are never fetched through the cache.
* ``maybeRvcMap`` is reported in the fetch coordinate (bit 0 = first instruction
  slot of request 0): each line's map is shifted and masked, a cross-line fetch
  is stitched from both lines, and request 1's contribution only exists when the
  second fetch is real.
* Two-fetch rule: the second fetch is real only when it is valid, its way-lookup
  entry is valid, and it does not collide with request 0 on a data-array bank
  with a different set but the same way (one set can be read per way per bank),
  and neither request is MMIO or has an ITLB exception.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Callable


FETCH_PORTS = 2
MAX_INST_PER_BLOCK = 32
DATA_BANKS = 8
UNTAG_BITS = 14          # address bits below the tag: set index + block offset
BLOCK_OFF_BITS = 6
INST_OFF_BITS = 1
FETCH_BLOCK_ALIGN_BITS = 5
PAGE_OFF_BITS = 12
PADDR_BITS = 48
INST_MASK = (1 << MAX_INST_PER_BLOCK) - 1
WORD_MASK = (1 << 64) - 1

EXC_NONE = 0
EXC_PF = 1
EXC_GPF = 2
EXC_AF = 3
EXC_HWE = 5


def get_idx(vaddr: int) -> int:
    """Virtual set index: vAddr[untagBits-1:blockOffBits]."""
    return (vaddr >> BLOCK_OFF_BITS) & ((1 << (UNTAG_BITS - BLOCK_OFF_BITS)) - 1)


def get_ptag(blk_paddr: int) -> int:
    return blk_paddr >> (PAGE_OFF_BITS - BLOCK_OFF_BITS)


def get_blk_addr(ptag: int, vaddr: int) -> int:
    return ((ptag << (PAGE_OFF_BITS - BLOCK_OFF_BITS))
            | ((vaddr >> BLOCK_OFF_BITS) & ((1 << (PAGE_OFF_BITS - BLOCK_OFF_BITS)) - 1)))


def get_paddr(ptag: int, vaddr: int) -> int:
    return ((ptag << PAGE_OFF_BITS) | (vaddr & ((1 << PAGE_OFF_BITS) - 1))) & ((1 << PADDR_BITS) - 1)


def is_pbmt_uncached(pbmt: int) -> bool:
    """PBMT=2/3 are the non-cacheable memory types (RISC-V Svpbmt)."""
    return (pbmt & 0b10) != 0


def is_cross_line(start_vaddr: int, end_position: int) -> int:
    """A 64-byte fetch aligned to 32 bytes crosses the line iff it ends past it."""
    return int(bool(start_vaddr & (1 << (BLOCK_OFF_BITS - 1)))
               and bool(end_position & (1 << (FETCH_BLOCK_ALIGN_BITS - 1))))


def gen_inst_range(size: int) -> int:
    if size >= MAX_INST_PER_BLOCK:
        return INST_MASK
    return (1 << size) - 1 if size > 0 else 0


def shift_maybe_rvc(raw: int, shift: int, left: bool) -> int:
    if left:
        return (raw << shift) & INST_MASK
    return (raw >> shift) & INST_MASK


def ftq_offset(start_vaddr: int, end_position: int) -> int:
    return (end_position - ((start_vaddr >> INST_OFF_BITS) & 0xF)) & 0x1F


@dataclass(frozen=True, slots=True)
class FetchRequest:
    vaddr: int
    next_vaddr: int
    end_position: int
    ftq_idx: int
    taken: int = 0
    bank_sel: tuple[int, int] = (0xFF, 0x00)
    vset: tuple[int, int] = (0, 0)
    has_backend_exception: int = 0
    has_satp_flush: int = 0
    backend_exception: int = 0
    valid: int = 1


@dataclass(frozen=True, slots=True)
class WayEntry:
    waymask: tuple[int, int]
    vset: tuple[int, int]
    ptag: int = 0
    rvc_map: tuple[int, int] = (0, 0)
    meta_codes: tuple[int, int] = (0, 0)
    is_mmio: int = 0
    itlb_pbmt: int = 0
    itlb_exception: int = 0
    gpaddr: int = 0
    vs_non_leaf: int = 0
    valid: int = 1
    # Optional explicit array image (one word per data bank).  A test uses it
    # to control the ECC parity of individual banks; None keeps the default
    # deterministic image.
    words: tuple[int, ...] | None = None


@dataclass(frozen=True, slots=True)
class MissResponse:
    block: int
    vset: int
    data: int
    waymask: int = 0
    maybe_rvc_map: int = 0
    corrupt: int = 0
    denied: int = 0


@dataclass(frozen=True, slots=True)
class IfuBlock:
    valid: int
    start_vaddr: int
    ftq_idx: int
    taken_valid: int
    taken_bits: int
    size: int
    data: int
    cross_line: int
    exception: int
    pmp_mmio: int
    backend_exception: int
    has_satp_flush: int
    vs_non_leaf: int
    itlb_pbmt: int
    paddr: int
    gpaddr: int


@dataclass(frozen=True, slots=True)
class Touch:
    req: int
    line: int
    vset: int
    way: int


@dataclass(frozen=True, slots=True)
class Outcome:
    two_fetch_valid: int
    ifu_valid: int
    maybe_rvc_map: int
    first_range: int
    total_range: int
    blocks: tuple[IfuBlock, IfuBlock]
    pending_miss: int
    raw_hits: tuple[int, int]
    touches: tuple[Touch, ...]
    missing_lines: tuple[tuple[int, int], ...] = field(default_factory=tuple)


def two_fetch_valid(req0: FetchRequest, req1: FetchRequest, way0: WayEntry,
                    way1: WayEntry) -> int:
    if not (req0.valid and req1.valid and way1.valid):
        return 0
    if way0.is_mmio or way1.is_mmio:
        return 0
    if way0.itlb_exception or way1.itlb_exception:
        return 0
    for l0 in range(FETCH_PORTS):
        for l1 in range(FETCH_PORTS):
            if (req0.bank_sel[l0] & req1.bank_sel[l1]
                    and way0.waymask[l0] == way1.waymask[l1]
                    and way0.vset[l0] != way1.vset[l1]):
                return 0
    return 1


def line_image(vset: int, way: int) -> tuple[int, ...]:
    """Deterministic per-bank word image produced by the data-array peer."""
    return tuple(
        ((vset & 0xFF) << 56) | ((way & 0b11) << 54) | (bank << 48) | 0x5A5A
        for bank in range(DATA_BANKS)
    )


def _hit_way(waymask: int) -> int:
    return (waymask & -waymask).bit_length() - 1


def predict(
    req0: FetchRequest,
    req1: FetchRequest,
    way0: WayEntry,
    way1: WayEntry,
    *,
    ptag: int | None = None,
    pmp_instr: int = 0,
    pmp_mmio: int = 0,
    miss: "MissResponse | list[MissResponse] | None" = None,
    word_source: "Callable[[int], tuple[int, ...]] | None" = None,
    data_array_banks: bool = False,
) -> Outcome:
    """Predict the response to one accepted fetch request pair."""
    page_tag = way0.ptag if ptag is None else ptag
    misses = ([miss] if isinstance(miss, MissResponse)
              else list(miss) if miss else [])
    two = two_fetch_valid(req0, req1, way0, way1)
    cross = (is_cross_line(req0.vaddr, req0.end_position),
             is_cross_line(req1.vaddr, req1.end_position))
    global_mmio = int(bool(pmp_mmio) or is_pbmt_uncached(way0.itlb_pbmt))

    touches: list[Touch] = []
    blocks: list[IfuBlock] = []
    missing: list[tuple[int, int]] = []
    mshr_hits: list[list[int]] = [[0, 0], [0, 0]]

    for req_index, (req, way) in enumerate(((req0, way0), (req1, way1))):
        effective = req.valid if req_index == 0 else two
        if not effective:
            blocks.append(IfuBlock(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
            continue

        mshr_lines = mshr_hits[req_index]
        tl_exception = 0
        line_refill: list[MissResponse | None] = [None, None]
        for line in range(FETCH_PORTS):
            if line == 1 and not cross[req_index]:
                continue
            for candidate in misses:
                if (candidate.vset == way.vset[line]
                        and get_ptag(candidate.block) == page_tag):
                    line_refill[line] = candidate
                    mshr_lines[line] = 1
                    if candidate.corrupt:
                        tl_exception = EXC_AF if candidate.denied else EXC_HWE
                    break

        exception = (way.itlb_exception or (EXC_AF if pmp_instr else EXC_NONE)
                     or tl_exception)

        # Data for each bank comes from the refill of the line that owns the
        # bank, or from the array image of a line that was already present.
        # A real data array only reads the banks selected by the FTQ bank mask,
        # while a refilled line bypasses the array completely and fills every
        # bank of its line.
        bank_low = (req.vaddr >> 3) & (DATA_BANKS - 1)
        banks: list[int] = [0] * DATA_BANKS
        for bank in range(DATA_BANKS):
            line = 1 if bank < bank_low else 0
            if line == 1 and not cross[req_index]:
                continue
            refill = line_refill[line]
            if refill is not None:
                banks[bank] = (refill.data >> (64 * bank)) & WORD_MASK
            elif way.waymask[line]:
                if data_array_banks and not ((req.bank_sel[line] >> bank) & 1):
                    continue
                if word_source is None:
                    words = (way.words if way.words is not None
                             else line_image(way.vset[line],
                                             _hit_way(way.waymask[line])))
                else:
                    vaddr = req.vaddr if line == 0 else req.next_vaddr
                    words = word_source(get_blk_addr(page_tag, vaddr))
                banks[bank] = words[bank]
        data = sum(bank << (64 * index) for index, bank in enumerate(banks))

        for line in range(FETCH_PORTS):
            line_valid = req.valid and (line == 0 or cross[req_index])
            if not line_valid:
                continue
            hit = bool(way.waymask[line]) or bool(mshr_lines[line])
            if hit:
                if way.waymask[line] and not mshr_lines[line]:
                    touches.append(Touch(req_index, line, way.vset[line],
                                         _hit_way(way.waymask[line])))
            elif exception == 0 and not global_mmio:
                missing.append((req_index, line))

        taken = ftq_offset(req.vaddr, req.end_position)
        blocks.append(IfuBlock(
            valid=1,
            start_vaddr=req.vaddr,
            ftq_idx=req.ftq_idx,
            taken_valid=req.taken,
            taken_bits=taken,
            size=(taken + 1) & 0x3F,
            data=data,
            cross_line=cross[req_index],
            exception=exception,
            # The IFU's pmpMmio field reports the PMP answer only; an
            # uncacheable PBMT is carried separately in itlbPbmt.
            pmp_mmio=int(bool(pmp_mmio)),
            backend_exception=req.has_backend_exception,
            has_satp_flush=req.has_satp_flush,
            vs_non_leaf=way.vs_non_leaf,
            itlb_pbmt=way0.itlb_pbmt,
            paddr=get_paddr(page_tag, req.vaddr) & ((1 << PADDR_BITS) - 1),
            gpaddr=way.gpaddr & ((1 << 55) - 1),
        ))

    # RVC alignment is expressed in the fetch coordinate.
    # Instruction-slot offset of the fetch start inside the cache line:
    # startVAddr[5:1].  The *size* uses the 32-byte fetch-block coordinate
    # (startVAddr[4:1]); the two coordinates differ when the fetch block starts
    # at offset 0x20 of the line, which is exactly the cross-line case.
    req_start = ((req0.vaddr >> 1) & 0x1F, (req1.vaddr >> 1) & 0x1F)
    sizes = (ftq_offset(req0.vaddr, req0.end_position) + 1,
             ftq_offset(req1.vaddr, req1.end_position) + 1)
    first_range = gen_inst_range(sizes[0])
    total_range = gen_inst_range(sizes[0] + sizes[1])

    shift0 = req_start[0]
    shift1 = 31 - req_start[0]
    shift_right = int(req_start[1] > sizes[0])
    shift2 = abs(req_start[1] - sizes[0])
    shift3 = (31 - req_start[1] + sizes[0] - 1) & 0x1F
    configs = ((0, False), (1, True), (0, not shift_right), (2, True))
    raw_maps = (way0.rvc_map[0], way0.rvc_map[1], way1.rvc_map[0], way1.rvc_map[1])
    shifts = (shift0, shift1, shift2, shift3)
    sram_aligned = [
        shift_maybe_rvc((raw << extra) & INST_MASK, shift, left)
        for raw, (extra, left), shift in zip(raw_maps, configs, shifts)
    ]

    # A refilled line's RVC map comes from the missUnit and is aligned with the
    # registered shift parameters; the array map is only used for lines that
    # were already present.
    req0_refill = next((candidate for candidate in misses
                        if (mshr_hits[0][0] or mshr_hits[0][1])
                        and (candidate.vset == way0.vset[0]
                             or candidate.vset == way0.vset[1])
                        and get_ptag(candidate.block) == page_tag), None)
    req1_refill = next((candidate for candidate in misses
                        if (mshr_hits[1][0] or mshr_hits[1][1])
                        and (candidate.vset == way1.vset[0]
                             or candidate.vset == way1.vset[1])
                        and get_ptag(candidate.block) == page_tag), None)
    refill_raw = req0_refill.maybe_rvc_map if req0_refill is not None else 0
    mshr_map0 = ((refill_raw >> shift0) if mshr_hits[0][0]
                 else ((refill_raw << 1) << shift1)) & INST_MASK
    raw1 = req1_refill.maybe_rvc_map if req1_refill is not None else 0
    mshr_map1 = ((((raw1 >> shift2) if shift_right else (raw1 << shift2))
                  if mshr_hits[1][0] else ((raw1 << 2) << shift3)) & INST_MASK)
    # One aligned miss map is shared by the two ports of a request, because a
    # request can be waiting on at most one line.
    aligned = [
        mshr_map0 if mshr_hits[0][0] else sram_aligned[0],
        mshr_map0 if mshr_hits[0][1] else sram_aligned[1],
        mshr_map1 if mshr_hits[1][0] else sram_aligned[2],
        mshr_map1 if mshr_hits[1][1] else sram_aligned[3],
    ]

    mask00 = gen_inst_range(MAX_INST_PER_BLOCK - shift0) & first_range
    mask01 = first_range & ~mask00 & INST_MASK
    req1_line0_end = (MAX_INST_PER_BLOCK - req_start[1] + sizes[0]) % (2 * MAX_INST_PER_BLOCK)
    mask10 = gen_inst_range(req1_line0_end) & total_range & ~first_range & INST_MASK
    mask11 = total_range & ~(first_range | mask10) & INST_MASK
    masks = (mask00, mask01, mask10 if two else 0, mask11 if two else 0)
    merged = 0
    for value, mask in zip(aligned, masks):
        merged |= value & mask

    return Outcome(
        two_fetch_valid=two,
        ifu_valid=int(not missing),
        maybe_rvc_map=merged,
        first_range=first_range,
        total_range=total_range if two else first_range,
        blocks=(blocks[0], blocks[1]),
        pending_miss=int(bool(missing)),
        raw_hits=(int(bool(way0.waymask[0])), int(bool(way0.waymask[1]))),
        touches=tuple(touches),
        missing_lines=tuple(missing),
    )


def expected_miss_request(req: FetchRequest, way: WayEntry, line: int,
                          ptag: int | None = None) -> tuple[int, int]:
    """Block address and set index the miss unit must receive for ``line``."""
    page_tag = way.ptag if ptag is None else ptag
    vaddr = req.vaddr if line == 0 else req.next_vaddr
    return get_blk_addr(page_tag, vaddr), way.vset[line]
