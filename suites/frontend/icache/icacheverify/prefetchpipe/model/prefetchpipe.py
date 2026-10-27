"""Functional reference model for ICachePrefetchPipe.

The prefetch pipe turns an FTQ prefetch request into a way-lookup entry and,
when the metadata has no match, into a miss-unit request. The model follows the
documented behaviour of that path:

* The FTQ request names one or two fetch blocks (the second only when
  ``twoPrefetchCase`` is non-zero). The selected case decides which two cache
  lines are read from the metadata array (two ports, one line each).
* The ITLB answer supplies one physical page tag, the memory type (PBMT) and
  the exception information. The metadata array is read with that tag; a way
  whose stored tag matches is a hit and its RVC map/code become the entry's.
* The way-lookup write carries, per fetch block, the set index of both lines,
  the per-line waymask, the shared page tag and the exception entry. A soft
  prefetch is not written to the way lookup (it must not steer the main pipe).
* For each metadata read port that has no hit (and is not an exception/MMIO),
  one miss request is issued, with the block address and set index of that read
  port. ``csrPfEnable`` gates entry to the request stage: with prefetching
  disabled the way lookup is still written but no miss is requested.
* An ITLB miss stalls the pipe and keeps re-issuing the translation request;
  ``pendingItlbMiss`` remains asserted. When the metadata read is not ready at
  the same time, it is re-issued as well.
* A flush kills the stage and flushes the ITLB pipe.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


PORTS = 2
WAYS = 4
UNTAG_BITS = 14
BLOCK_OFF_BITS = 6
PAGE_OFF_BITS = 12

EXC_NONE = 0
EXC_PF = 1
EXC_GPF = 2
EXC_AF = 3


def get_idx(vaddr: int) -> int:
    return (vaddr >> BLOCK_OFF_BITS) & ((1 << (UNTAG_BITS - BLOCK_OFF_BITS)) - 1)


def get_blk_addr(ptag: int, vaddr: int) -> int:
    return ((ptag << (PAGE_OFF_BITS - BLOCK_OFF_BITS))
            | ((vaddr >> BLOCK_OFF_BITS) & ((1 << (PAGE_OFF_BITS - BLOCK_OFF_BITS)) - 1)))


def get_ptag(blk_paddr: int) -> int:
    return blk_paddr >> (PAGE_OFF_BITS - BLOCK_OFF_BITS)


def is_pbmt_uncached(pbmt: int) -> bool:
    """Svpbmt: 00=PMA, 01=NC, 10=IO, 11=reserved (XiangShan ``Pbmt``).

    NC and IO are non-cacheable; the reserved encoding is not a defined
    uncacheable attribute.
    """
    return pbmt in (1, 2)


def is_cross_line(start_vaddr: int, end_position: int) -> int:
    return int(bool(start_vaddr & 0x20) and bool(end_position & 0x10))


def ftq_offset(start_vaddr: int, end_position: int) -> int:
    return (end_position - ((start_vaddr >> 1) & 0xF)) & 0x1F


@dataclass(frozen=True, slots=True)
class PrefetchRequest:
    vaddr: int
    next_vaddr: int
    end_position: int
    ftq_idx: int
    is_cross_line: int = 0
    is_soft_prefetch: int = 0
    backend_exception: int = 0
    vset: tuple[int, int] = (0, 0)


@dataclass(frozen=True, slots=True)
class ItlbResponse:
    miss: int = 0
    paddr: int = 0
    pbmt: int = 0
    gpaddr: int = 0
    pf: int = 0
    af: int = 0
    gpf: int = 0
    vs_non_leaf: int = 0


@dataclass(frozen=True, slots=True)
class MetaEntry:
    ptag: int
    rvc: int = 0
    code: int = 0
    valid: int = 1


@dataclass(frozen=True, slots=True)
class WayWrite:
    valid: int
    ftq_idx: int
    vset: tuple[int, int]
    waymask: tuple[int, int]
    ptag: int
    rvc: tuple[int, int]
    code: tuple[int, int]
    is_mmio: int
    itlb_pbmt: int
    exception: int
    gpaddr: int
    vs_non_leaf: int


@dataclass(frozen=True, slots=True)
class Outcome:
    writes: tuple[WayWrite, WayWrite]
    misses: tuple[tuple[int, int], ...]
    meta_sets: tuple[int, int]
    meta_double: int
    itlb_vaddr: int
    pending_itlb_miss: int
    # A fetch reads its second line only when it crosses the cache line.  The
    # second slot's waymask/RVC map/parity are then meaningful; otherwise the
    # pipe may present stale register contents and the fields are don't-care.
    line1_valid: tuple[int, int] = (1, 1)


# TwoPrefetchCase value bits
CASE_CONFLICT = 0
CASE_SAME_LINE = 1
CASE_OVERLAP1 = 2
CASE_OVERLAP2 = 4
CASE_INTERLEAVE = 8


def select_meta_vaddr(case: int, req0: PrefetchRequest,
                      req1: PrefetchRequest) -> tuple[int, int]:
    if case & CASE_OVERLAP2:
        return req1.vaddr, req1.next_vaddr
    if case & CASE_INTERLEAVE:
        return req0.vaddr, req1.vaddr
    return req0.vaddr, req0.next_vaddr


def select_meta_set(case: int, req0: PrefetchRequest,
                    req1: PrefetchRequest) -> tuple[int, int]:
    if case & CASE_OVERLAP2:
        return req1.vset
    if case & CASE_INTERLEAVE:
        return req0.vset[0], req1.vset[0]
    return req0.vset


def select_double(case: int, req0: PrefetchRequest, req1: PrefetchRequest) -> int:
    if case & CASE_SAME_LINE:
        return int(bool(req0.is_cross_line or req1.is_cross_line))
    if case & (CASE_OVERLAP1 | CASE_OVERLAP2 | CASE_INTERLEAVE):
        return 1
    return int(bool(req0.is_cross_line))


def itlb_exception(resp: ItlbResponse) -> int:
    if resp.pf:
        return EXC_PF
    if resp.gpf:
        return EXC_GPF
    if resp.af:
        return EXC_AF
    return EXC_NONE


def waymask_of(ptag: int, entries: tuple[MetaEntry, ...]) -> int:
    mask = 0
    for way, entry in enumerate(entries):
        if entry.valid and entry.ptag == ptag:
            mask |= 1 << way
    return mask


def selected_meta(ptag: int, entries: tuple[MetaEntry, ...]) -> tuple[int, int, int]:
    mask = waymask_of(ptag, entries)
    if mask == 0:
        return 0, 0, 0
    way = (mask & -mask).bit_length() - 1
    return mask, entries[way].rvc, entries[way].code


def _broadcast(case: int, read: list[tuple[int, int, int]]
               ) -> list[tuple[tuple[int, int, int], tuple[int, int, int]]]:
    """Per-fetch (line0, line1) metadata from the two read ports."""
    zero = (0, 0, 0)
    if case & CASE_OVERLAP2:
        return [(read[1], zero), (read[0], read[1])]
    if case & CASE_INTERLEAVE:
        return [(read[0], zero), (read[1], zero)]
    if case & CASE_SAME_LINE:
        return [(read[0], read[1]), (read[0], read[1])]
    if case & CASE_OVERLAP1:
        return [(read[0], read[1]), (read[1], zero)]
    return [(read[0], read[1]), (zero, zero)]


def predict(
    req0: PrefetchRequest,
    req1: PrefetchRequest,
    *,
    case: int = CASE_CONFLICT,
    itlb: ItlbResponse | None = None,
    meta: tuple[tuple[MetaEntry, ...], tuple[MetaEntry, ...]] | None = None,
    pmp_instr: int = 0,
    pmp_mmio: int = 0,
    pf_enable: int = 1,
) -> Outcome:
    itlb = itlb or ItlbResponse()
    meta = meta or ((), ())
    ptag = itlb.paddr >> PAGE_OFF_BITS
    # The speculative way-lookup entry is written in stage 1, so it can carry
    # only the translation/backend exception known there.  PMP is a stage-2
    # check (the RTL consumes ``pmp_resp_instr`` when the miss request is
    # formed); it suppresses the prefetch request but is not stored in the
    # entry, because a later demand fetch re-checks PMP for its own address.
    write_exception = req0.backend_exception or itlb_exception(itlb)
    exception = write_exception or (EXC_AF if pmp_instr else EXC_NONE)
    mmio = int(bool(pmp_mmio) or is_pbmt_uncached(itlb.pbmt))

    meta_sets = select_meta_set(case, req0, req1)
    meta_vaddrs = select_meta_vaddr(case, req0, req1)
    double = select_double(case, req0, req1)

    read_info = [selected_meta(ptag, entries) for entries in meta]
    # The second metadata port is only sampled for a double-line read; its
    # registered fallback keeps whatever the previous transaction left there,
    # which a fresh pipeline sees as zero.
    if not double:
        read_info[1] = (0, 0, 0)
    broadcast = _broadcast(case, read_info)

    def line_write(req: PrefetchRequest, index: int, valid: int) -> WayWrite:
        line0, line1 = broadcast[index]
        return WayWrite(
            valid=valid,
            ftq_idx=req.ftq_idx,
            vset=(get_idx(req.vaddr), get_idx(req.next_vaddr)),
            waymask=(line0[0], line1[0]),
            ptag=ptag,
            rvc=(line0[1], line1[1]),
            code=(line0[2], line1[2]),
            is_mmio=mmio,
            itlb_pbmt=itlb.pbmt,
            exception=write_exception,
            gpaddr=(((itlb.gpaddr >> PAGE_OFF_BITS) << PAGE_OFF_BITS)
                    | (req.vaddr & ((1 << PAGE_OFF_BITS) - 1))) & ((1 << 55) - 1),
            vs_non_leaf=itlb.vs_non_leaf,
        )

    writes = (line_write(req0, 0, int(not req0.is_soft_prefetch)),
              line_write(req1, 1, int(bool(case) and not req1.is_soft_prefetch)))

    misses: list[tuple[int, int]] = []
    if pf_enable and exception == EXC_NONE and not mmio:
        for port in range(PORTS):
            if port == 1 and not double:
                continue
            if read_info[port][0]:
                continue
            misses.append((get_blk_addr(ptag, meta_vaddrs[port]), meta_sets[port]))

    return Outcome(
        writes=writes,
        misses=tuple(misses),
        meta_sets=meta_sets,
        meta_double=double,
        itlb_vaddr=meta_vaddrs[0],
        pending_itlb_miss=int(bool(itlb.miss)),
        line1_valid=(int(req0.is_cross_line),
                     int(bool(req1.is_cross_line and case))),
    )
