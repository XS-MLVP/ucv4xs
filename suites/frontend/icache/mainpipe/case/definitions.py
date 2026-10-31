"""Request construction helpers shared by the MainPipe test cases."""

from __future__ import annotations

from suites.frontend.icache.mainpipe.model.mainpipe import DATA_BANKS
from suites.frontend.icache.mainpipe.model.mainpipe import FetchRequest
from suites.frontend.icache.mainpipe.model.mainpipe import WayEntry
from suites.frontend.icache.mainpipe.model.mainpipe import get_idx
from suites.frontend.icache.mainpipe.model.mainpipe import is_cross_line
from suites.frontend.icache.mainpipe.model.mainpipe import line_image


def bank_sel(start_vaddr: int, end_position: int) -> tuple[int, int]:
    """Data-bank mask per line, as the FTQ computes it for a fetch block."""
    low = (start_vaddr >> 3) & 0x7
    cross = is_cross_line(start_vaddr, end_position)
    high = ((((start_vaddr >> 5) & 1) ^ ((end_position >> 4) & 1)) << 2
            | ((end_position >> 3) & 1) << 1
            | ((end_position >> 2) & 1))
    first = sum(1 << bank for bank in range(DATA_BANKS)
                if bank >= low and (cross or bank <= high))
    second = sum(1 << bank for bank in range(DATA_BANKS)
                 if cross and bank <= high)
    return first, second


def make_fetch(vaddr: int, end_position: int, ftq_idx: int = 0, *,
               taken: int = 0, valid: int = 1,
               has_satp_flush: int = 0,
               has_backend_exception: int = 0,
               backend_exception: int = 0,
               vset: tuple[int, int] | None = None) -> FetchRequest:
    if vset is None:
        # The FTQ always names the next line's set as startVAddr + 1; it is only
        # *used* when the fetch crosses the line.
        vset = (get_idx(vaddr), (get_idx(vaddr) + 1) & 0xFF)
    return FetchRequest(
        vaddr=vaddr,
        next_vaddr=vaddr + 64,
        end_position=end_position,
        ftq_idx=ftq_idx,
        taken=taken,
        bank_sel=bank_sel(vaddr, end_position),
        vset=vset,
        has_satp_flush=has_satp_flush,
        has_backend_exception=has_backend_exception,
        backend_exception=backend_exception,
        valid=valid,
    )


def make_way(req: FetchRequest, ptag: int, waymask: tuple[int, int],
             *, rvc_map: tuple[int, int] = (0xFFFF_FFFF, 0xFFFF_FFFF),
             itlb_exception: int = 0, is_mmio: int = 0, itlb_pbmt: int = 0,
             gpaddr: int = 0,
             words: tuple[int, ...] | None = None) -> WayEntry:
    return WayEntry(
        waymask=waymask,
        vset=req.vset,
        ptag=ptag,
        rvc_map=rvc_map,
        itlb_exception=itlb_exception,
        is_mmio=is_mmio,
        itlb_pbmt=itlb_pbmt,
        gpaddr=gpaddr,
        words=words,
    )


def data_word(vset: int, way: int) -> int:
    """The 512-bit line image the data-array peer returns."""
    return sum(word << (64 * bank)
               for bank, word in enumerate(line_image(vset, way)))
