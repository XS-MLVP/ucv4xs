"""Request construction helpers shared by the whole-ICache test cases."""

from __future__ import annotations

from suites.frontend.icache.testbenches.icache.model.icache import ICacheIntegrationModel
from suites.frontend.icache.testbenches.icache.model.icache import ItlbAnswer
from suites.frontend.icache.testbenches.icache.model.icache import get_idx
from suites.frontend.icache.testbenches.icache.model.icache import is_cross_line
from suites.frontend.icache.testbenches.icache.model.icache import CASE_CONFLICT
from suites.frontend.icache.testbenches.icache.model.icache import CASE_SAME_LINE
from suites.frontend.icache.testbenches.icache.model.icache import CASE_OVERLAP1
from suites.frontend.icache.testbenches.icache.model.icache import CASE_OVERLAP2
from suites.frontend.icache.testbenches.icache.model.icache import CASE_INTERLEAVE
from suites.frontend.icache.testbenches.icache.model.icache import prefetch_case
from suites.frontend.icache.testbenches.icache.transactions.types import SOURCE_FDIP
from suites.frontend.icache.testbenches.icache.transactions.types import SOURCE_SW
from suites.frontend.icache.testbenches.mainpipe.tests.scenarios.definitions import bank_sel
from suites.frontend.icache.testbenches.mainpipe.model.mainpipe import FetchRequest


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

