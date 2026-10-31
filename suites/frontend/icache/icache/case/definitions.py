"""Request construction helpers shared by the whole-ICache test cases."""

from __future__ import annotations

from suites.frontend.icache.icache.model.icache import ICacheIntegrationModel
from suites.frontend.icache.icache.model.icache import ItlbAnswer
from suites.frontend.icache.icache.model.icache import get_idx
from suites.frontend.icache.icache.model.icache import is_cross_line
from suites.frontend.icache.mainpipe.case.definitions import bank_sel
from suites.frontend.icache.mainpipe.model.mainpipe import FetchRequest


def make_fetch(vaddr: int, end_position: int, ftq_idx: int = 0, *,
               taken: int = 0, valid: int = 1,
               has_backend_exception: int = 0) -> FetchRequest:
    return FetchRequest(
        vaddr=vaddr,
        next_vaddr=vaddr + 64,
        end_position=end_position,
        ftq_idx=ftq_idx,
        taken=taken,
        bank_sel=bank_sel(vaddr, end_position),
        # The FTQ always names the next line's set as startVAddr + 1; it is only
        # used when the fetch crosses the line.
        vset=(get_idx(vaddr), (get_idx(vaddr) + 1) & 0xFF),
        has_backend_exception=has_backend_exception,
        valid=valid,
    )


def translate_identity(vaddr: int) -> ItlbAnswer:
    """Identity translation in 4 KiB pages (the default peer behaviour)."""
    return ItlbAnswer(paddr=vaddr & ((1 << 48) - 1))


def translate_to(paddr_page: int, offset_mask: int = 0xFFF):
    """Translate every page to ``paddr_page`` (same page offset)."""
    def translate(vaddr: int) -> ItlbAnswer:
        return ItlbAnswer(paddr=(paddr_page & ~offset_mask)
                          | (vaddr & offset_mask))
    return translate


CASE_CONFLICT = 0
CASE_SAME_LINE = 1
CASE_OVERLAP1 = 2
CASE_OVERLAP2 = 4
CASE_INTERLEAVE = 8


def prefetch_case(req0: FetchRequest, req1: FetchRequest) -> int:
    """The FTQ's two-prefetch classification for a request pair.

    Mirrors the published rule: two blocks that start in the same interleaved
    bank cannot be read together (Conflict); otherwise the pair is classified by
    whether the two blocks share a line, whether one is the other's next line,
    or whether they sit in the two interleaved banks.  The two fetches of one
    issue must share a 4 KiB page, and two different blocks never share a
    virtual set index.
    """
    if not req1.valid:
        return CASE_CONFLICT
    v0 = req0.vset[0]
    v1 = req1.vset[0]
    if v0 == v1:
        return CASE_SAME_LINE
    cross0 = is_cross_line(req0.vaddr, req0.end_position)
    cross1 = is_cross_line(req1.vaddr, req1.end_position)
    if cross0 and not cross1 and req0.vset[1] == v1:
        return CASE_OVERLAP1
    if not cross0 and cross1 and req1.vset[1] == v0:
        return CASE_OVERLAP2
    if not cross0 and not cross1 and (v0 & 1) != (v1 & 1):
        return CASE_INTERLEAVE
    return CASE_CONFLICT
