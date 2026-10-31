"""Integration reference model for the whole ICache.

The model is the architectural contract of an instruction cache, not a
transcription of the RTL:

* The cache is set-associative (256 sets x 4 ways x 64 B lines) and virtually
  indexed / physically tagged (4 KiB pages).  A line is identified by its
  physical page tag and virtual set index; both must match for a hit.
* A fetch reads the line(s) that cover the requested instruction window and
  returns the instruction bytes plus the fetch metadata.  The bytes of a
  physical block are fixed: memory content may not depend on which way the block
  happens to be cached in.
* An access to a resident line hits and does not touch the memory bus; an access
  to a non-resident line misses, requests the block from memory, installs it in
  the way named by the replacement policy, and returns the refill.
* The replacement policy is tree-PLRU with one instance per fetch port, keyed by
  the low bit of the set index (the ICacheReplacer contract, verified
  separately).  Choosing a victim marks it as most-recently used, so two
  consecutive fills select different ways.
* ``fence.i`` invalidates the whole array (the ISA requires the instruction
  stream to be re-fetched after a fence.i).
* A redirect flush discards a fetch that has not reached the IFU yet.
* ITLB/PMP exceptions are reported instead of data; MMIO and uncacheable memory
  types are never cached.
* A prefetch (hardware or software) only warms the array: it produces no IFU
  response, but the next fetch of that block hits.

The response itself (bank selection, RVC-map alignment, exception fields) is
computed by the already-validated MainPipe model, with the array content supplied
by :func:`memory_line` so that it depends on the physical block only.
"""

from __future__ import annotations

from dataclasses import dataclass

from suites.frontend.icache.mainpipe.model import mainpipe as mp
from suites.frontend.icache.mainpipe.model.mainpipe import FetchRequest
from suites.frontend.icache.mainpipe.model.mainpipe import MissResponse
from suites.frontend.icache.mainpipe.model.mainpipe import Outcome
from suites.frontend.icache.mainpipe.model.mainpipe import WayEntry
from suites.frontend.icache.replacer.model.plru import PortPlru


NUM_SETS = 256
NUM_WAYS = 4
PORTS = 2
SETS_PER_PORT = NUM_SETS // PORTS
DATA_BANKS = 8
WORD_MASK = (1 << 64) - 1
BLOCK_OFF_BITS = 6
PAGE_OFF_BITS = 12

EXC_NONE = mp.EXC_NONE
EXC_PF = mp.EXC_PF
EXC_GPF = mp.EXC_GPF
EXC_AF = mp.EXC_AF
EXC_HWE = mp.EXC_HWE


def get_idx(vaddr: int) -> int:
    return mp.get_idx(vaddr)


def get_ptag(block: int) -> int:
    return block >> (PAGE_OFF_BITS - BLOCK_OFF_BITS)


def get_blk_addr(ptag: int, vaddr: int) -> int:
    return mp.get_blk_addr(ptag, vaddr)


def is_cross_line(start_vaddr: int, end_position: int) -> int:
    return mp.is_cross_line(start_vaddr, end_position)


def is_pbmt_uncached(pbmt: int) -> bool:
    return mp.is_pbmt_uncached(pbmt)


@dataclass(frozen=True, slots=True)
class ItlbAnswer:
    """The translation the ITLB returns for one virtual address."""

    paddr: int
    miss: int = 0
    pbmt: int = 0
    gpaddr: int = 0
    pf: int = 0
    gpf: int = 0
    af: int = 0
    vs_non_leaf: int = 0

    @property
    def ptag(self) -> int:
        return self.paddr >> PAGE_OFF_BITS


def itlb_exception(resp: ItlbAnswer) -> int:
    """Instruction page fault / guest page fault / access fault, in that order."""
    if resp.pf:
        return EXC_PF
    if resp.gpf:
        return EXC_GPF
    if resp.af:
        return EXC_AF
    return EXC_NONE


# ---------------------------------------------------------------------------
# Memory image
# ---------------------------------------------------------------------------
def memory_word(block: int, bank: int, variant: int = 0) -> int:
    """Word returned by memory for bank ``bank`` of physical block ``block``.

    Every 16-bit half-word has 0b10 in its low two bits, so the default line
    looks like all-compressed instructions.  ``variant=1`` plants 32-bit
    instruction markers in the first bank of odd blocks so the RVC map is not
    uniform and alignment can be checked.
    """
    word = 0x5A5A5A5A5A5A5A5A
    word ^= (block & 0xFF) << 40
    word ^= (bank & 0xFF) << 8
    if variant and (block & 1) and bank == 0:
        word = (word & ~0xFFFF_0000_FFFF_0000) | 0x0003_0000_0013_0000
    return word & WORD_MASK


def memory_line(block: int, variant: int = 0) -> tuple[int, ...]:
    return tuple(memory_word(block, bank, variant) for bank in range(DATA_BANKS))


def memory_data(block: int, variant: int = 0) -> int:
    """512-bit refill payload, bank 0 in the least significant bits."""
    return sum(word << (64 * bank)
               for bank, word in enumerate(memory_line(block, variant)))


def rvc_map_of(block: int, variant: int = 0) -> int:
    """Per-line compressed-instruction map: bit i = slot i's low bits != 0b11."""
    line = memory_line(block, variant)
    out = 0
    for slot in range(32):
        half = (line[slot // 4] >> (16 * (slot % 4))) & 0xFFFF
        if (half & 0b11) != 0b11:
            out |= 1 << slot
    return out


# ---------------------------------------------------------------------------
# Cache state
# ---------------------------------------------------------------------------
@dataclass
class LineState:
    valid: int = 0
    ptag: int = 0
    block: int = 0
    rvc_map: int = 0


@dataclass(frozen=True, slots=True)
class Fill:
    """One refill the memory peer must deliver."""

    block: int
    vset: int
    data: int
    maybe_rvc_map: int
    req: int
    line: int
    corrupt: int = 0
    denied: int = 0


@dataclass(frozen=True, slots=True)
class Expectation:
    outcome: Outcome
    fills: tuple[Fill, ...]
    touches: tuple[mp.Touch, ...]
    hit: tuple[int, int]
    # Banks whose value is architecturally determined: the banks inside the
    # fetch range (read from the array) and every bank of a refilled line (the
    # refill bypasses the array).  Banks of a line that is not part of this
    # fetch keep whatever the array read register last held and are don't-care.
    data_masks: tuple[int, int] = (0, 0)

    @property
    def fill_blocks(self) -> tuple[int, ...]:
        return tuple(fill.block for fill in self.fills)

    @property
    def fill_by_block(self) -> dict[int, Fill]:
        return {fill.block: fill for fill in self.fills}


class ICacheIntegrationModel:
    def __init__(self, variant: int = 0) -> None:
        self.variant = variant
        self.lines: list[list[LineState]] = [
            [LineState() for _ in range(NUM_WAYS)] for _ in range(NUM_SETS)
        ]
        # One independent tree-PLRU per fetch port, keyed by vSetIdx[0].
        self.replacers = [PortPlru(SETS_PER_PORT, NUM_WAYS) for _ in range(PORTS)]
        self.fills_served: list[int] = []
        self.fetch_count = 0

    # -- replacement --------------------------------------------------------
    @staticmethod
    def replacer_of(vset: int) -> int:
        return vset & (PORTS - 1)

    @staticmethod
    def replacer_set(vset: int) -> int:
        return (vset >> 1) % SETS_PER_PORT

    def hit_way(self, block: int, vset: int) -> int | None:
        ptag = get_ptag(block)
        for way, line in enumerate(self.lines[vset]):
            if line.valid and line.ptag == ptag:
                return way
        return None

    def hit_mask(self, block: int, vset: int) -> int:
        way = self.hit_way(block, vset)
        return 0 if way is None else 1 << way

    def victim(self, vset: int) -> int:
        return self.replacers[self.replacer_of(vset)].victim(
            self.replacer_set(vset))

    def install(self, block: int, vset: int) -> int:
        way = self.victim(vset)
        # The replacement decision is fed back as a touch on the next edge, so
        # the next fill in the same set picks a different way.
        self.replacers[self.replacer_of(vset)].touch(
            self.replacer_set(vset), way)
        self.lines[vset][way] = LineState(
            valid=1, ptag=get_ptag(block), block=block,
            rvc_map=rvc_map_of(block, self.variant))
        return way

    def touch(self, vset: int, way: int) -> None:
        self.replacers[self.replacer_of(vset)].touch(
            self.replacer_set(vset), way)

    def invalidate_all(self) -> None:
        self.lines = [[LineState() for _ in range(NUM_WAYS)]
                      for _ in range(NUM_SETS)]
        self.replacers = [PortPlru(SETS_PER_PORT, NUM_WAYS) for _ in range(PORTS)]

    # -- expectation --------------------------------------------------------
    def _way_entry(self, req: FetchRequest, ptag: int, itlb: ItlbAnswer,
                   exception: int, mmio: int, gpaddr: int = 0) -> WayEntry:
        if not req.valid:
            return WayEntry(waymask=(0, 0), vset=(0, 0), valid=0)
        cross = is_cross_line(req.vaddr, req.end_position)
        masks: list[int] = []
        maps: list[int] = []
        for line in range(PORTS):
            if line == 1 and not cross:
                masks.append(0)
                maps.append(0)
                continue
            vaddr = req.vaddr if line == 0 else req.next_vaddr
            block = get_blk_addr(ptag, vaddr)
            mask = self.hit_mask(block, req.vset[line])
            masks.append(mask)
            # The way-lookup map comes from the metadata array: a line that is
            # not resident contributes no map.
            maps.append(rvc_map_of(block, self.variant) if mask else 0)
        return WayEntry(
            waymask=(masks[0], masks[1]),
            vset=req.vset,
            ptag=ptag,
            rvc_map=(maps[0], maps[1]),
            itlb_exception=exception,
            itlb_pbmt=itlb.pbmt,
            is_mmio=mmio,
            gpaddr=gpaddr & ((1 << 55) - 1),
            vs_non_leaf=itlb.vs_non_leaf,
        )

    def expect(
        self,
        req0: FetchRequest,
        req1: FetchRequest,
        *,
        itlb: ItlbAnswer,
        pmp_instr: int = 0,
        pmp_mmio: int = 0,
        corrupt_refill: int = 0,
        denied_refill: int = 0,
    ) -> Expectation:
        """Predict the IFU response and the refills that must be requested."""
        ptag = itlb.ptag
        exception = (req0.backend_exception or itlb_exception(itlb)
                     or (EXC_AF if pmp_instr else EXC_NONE))
        mmio = int(bool(pmp_mmio) or is_pbmt_uncached(itlb.pbmt))

        # The guest address is only published with an ITLB/back-end exception;
        # its page offset comes from the fetched virtual address.
        has_fault_entry = bool(itlb_exception(itlb) or req0.backend_exception)
        gpaddr = (((itlb.gpaddr & ~0xFFF) | (req0.vaddr & 0xFFF))
                  if has_fault_entry else 0)
        way0 = self._way_entry(req0, ptag, itlb, exception, mmio, gpaddr)
        way1 = self._way_entry(req1, ptag, itlb, exception, mmio, gpaddr)

        before = mp.predict(
            req0, req1, way0, way1, pmp_instr=pmp_instr, pmp_mmio=pmp_mmio,
            miss=None,
            word_source=lambda block: memory_line(block, self.variant),
            data_array_banks=True,
        )
        fills: list[Fill] = []
        for req_index, line in before.missing_lines:
            req = req0 if req_index == 0 else req1
            vaddr = req.vaddr if line == 0 else req.next_vaddr
            block = get_blk_addr(ptag, vaddr)
            fills.append(Fill(
                block=block,
                vset=req.vset[line],
                data=memory_data(block, self.variant),
                maybe_rvc_map=rvc_map_of(block, self.variant),
                req=req_index,
                line=line,
                corrupt=int(bool(corrupt_refill) or bool(denied_refill)),
                denied=int(bool(denied_refill)),
            ))

        outcome = mp.predict(
            req0, req1, way0, way1, pmp_instr=pmp_instr, pmp_mmio=pmp_mmio,
            miss=[MissResponse(block=f.block, vset=f.vset, data=f.data,
                               maybe_rvc_map=f.maybe_rvc_map,
                               corrupt=f.corrupt, denied=f.denied)
                  for f in fills],
            word_source=lambda block: memory_line(block, self.variant),
            data_array_banks=True,
        )
        refilled = {(fill.req, fill.line) for fill in fills}

        def request_mask(index: int, req: FetchRequest) -> int:
            if not req.valid:
                return 0
            low = (req.vaddr >> 3) & (DATA_BANKS - 1)
            cross = is_cross_line(req.vaddr, req.end_position)
            mask = 0
            for bank in range(DATA_BANKS):
                line = 1 if bank < low else 0
                if line == 1 and not cross:
                    continue
                if (index, line) in refilled:
                    mask |= 1 << bank
                elif (req.bank_sel[line] >> bank) & 1:
                    mask |= 1 << bank
            return mask

        return Expectation(
            outcome=outcome,
            fills=tuple(fills),
            touches=outcome.touches,
            hit=(int(bool(way0.waymask[0])), int(bool(way0.waymask[1]))),
            data_masks=(request_mask(0, req0), request_mask(1, req1)),
        )

    # -- state updates ------------------------------------------------------
    def commit_fill(self, fill: Fill) -> int:
        """Install a refilled block; returns the way it landed in."""
        way = self.install(fill.block, fill.vset)
        self.fills_served.append(fill.block)
        return way

    def commit_hit(self, touch: mp.Touch) -> None:
        self.touch(touch.vset, touch.way)
