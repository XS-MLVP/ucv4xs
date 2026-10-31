"""Reusable way-lookup entries.

Tags are distinct per entry so a test can prove FIFO ordering and that no entry
is lost, duplicated or resurrected by a flush.
"""

from __future__ import annotations

from suites.frontend.icache.waylookup.model.queue import idx_from_block
from suites.frontend.icache.waylookup.model.queue import ptag_from_block
from suites.frontend.icache.waylookup.transaction.types import ItlbException
from suites.frontend.icache.waylookup.transaction.types import WayLookupEntry


def entry_for_block(blk_paddr: int, *, waymask: int = 0b0001,
                    maybe_rvc_map: int = 0, exception: bool = False) -> WayLookupEntry:
    """Entry describing the way a TLB lookup predicted for one block.

    The set index and physical tag are *derived* from the block address, as the
    hardware does, so a later refill of the same block naturally has a matching
    tag. This is the architecture-level way to build the stimulus.
    """
    idx = idx_from_block(blk_paddr)
    entry = WayLookupEntry(
        vset_idx=(idx, idx),
        waymask=(waymask, waymask),
        ptag=ptag_from_block(blk_paddr),
        maybe_rvc_map=(maybe_rvc_map, maybe_rvc_map),
        meta_codes=(0, 0),
        is_mmio=0,
        itlb_pbmt=0,
        exception=ItlbException(value=1 if exception else 0, gpaddr=0x1000 * (idx + 1)),
    )
    return entry


def entry(tag: int, *, exception: bool = False) -> WayLookupEntry:
    """Build an entry whose payload is unique and cheap to compare."""
    return WayLookupEntry(
        vset_idx=(tag & 0xFF, (tag >> 8) & 0xFF),
        waymask=(tag & 0xF, (tag >> 4) & 0xF),
        ptag=tag,
        maybe_rvc_map=(tag & 0xFFFF, (tag >> 16) & 0xFFFF),
        meta_codes=(tag & 1, (tag >> 1) & 1),
        is_mmio=(tag >> 2) & 1,
        itlb_pbmt=(tag >> 3) & 0x3,
        exception=ItlbException(
            value=1 if exception else 0,
            gpaddr=((tag << 12) & 0x7FFF_FFFF_FFFF) | 0x1000,
            is_for_vs_non_leaf_pte=int(exception) & ((tag >> 5) & 1),
        ),
    )


def block(tag_index: int, set_index: int) -> int:
    """Block address with a chosen physical tag and set index.

    Parameterisation matters here. With 256 sets, 64-byte blocks and 4 KiB
    pages, the page number is ``pAddr >> 12`` while the set index is
    ``pAddr[13:6]``; the two overlap in bits 12-13. So the set index is not
    freely choosable for a given tag: its top two bits must equal the tag's low
    two bits. This helper derives a consistent tag from ``tag_index`` and
    ``set_index`` instead of letting a test build an address the hardware can
    never produce.
    """
    tag = (tag_index << 2) | ((set_index >> 6) & 0x3)
    return (tag << 6) | (set_index & 0xFF)
