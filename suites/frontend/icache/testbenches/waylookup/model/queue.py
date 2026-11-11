"""Reference model for ICacheWayLookup.

Semantics are derived from architecture and published specifications, not from
the RTL:

* **Circular FIFO** - a queue of ``PrefetchDepth`` slots addressed by a pointer
  with a wrap flag; ``n`` bytes of capacity require ``ceil(log2(depth))`` index
  bits plus one wrap bit (standard circular-buffer addressing, e.g. Lampson,
  "A note on the circular buffer", CACM 1978; also the textbook ring-buffer
  discipline).
* **Write readiness reserves one dual-port beat** - the prefetch side may
  publish up to ``FetchPorts`` entries per cycle, so a queue may only advertise
  ready while ``free >= FetchPorts`` even when only one port is used.
  Otherwise a simultaneous second port could be accepted without space.
* **Fill-completion update** - the way lookup memoises, per prefetched block,
  which set/way the TLB lookup said the block would occupy. When the miss unit
  later completes a refill the memo must be corrected: a matching physical tag
  adopts the actually-filled way and the per-block RVC map; a differing tag
  that occupies the memoised way invalidates that way (the line was replaced,
  so the pending fetch is a miss); unrelated refills are ignored. This is the
  cache-coherence rule "a line you do not own cannot be hit", applied to a
  speculative lookup memo rather than to a data array.
* **Update/read hazard** - while a memo entry's metadata is rewritten it is
  not safe to hand it downstream, so that entry is held back for one cycle.
  This is a standard read-after-write hazard rule for a single-ported memo.
* **Flush precedence** - a pipeline flush discards speculative state; a
  stage-3 redirect only unwinds the youngest entry, and only if that entry's
  FTQ block is on the wrong side of the redirect point (``not after`` the
  redirect index, since the redirect block itself is re-fetched).

``tailFtqIdx`` records the FTQ block of the youngest accepted entry so the
stage-3 comparison does not need to walk the queue.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


FETCH_PORTS = 2
FTQ_ENTRIES = 64


def ptag_from_block(blk_paddr: int) -> int:
    """Physical tag of a block address.

    ``blk_paddr`` is a byte address shifted down by the block offset, i.e.
    ``pAddr >> blockOffBits``. The tag is the address above the page index, so
    ``tag = blk_paddr >> (pgIdxBits - blockOffBits)``. For the default
    configuration (blockOffBits = 6, pgIdxBits = 12) this is ``blk_paddr >> 6``.
    """
    return blk_paddr >> 6


def idx_from_block(blk_paddr: int) -> int:
    """Set index of a block address, ``blk_paddr[idxBits-1:0]``."""
    return blk_paddr & 0xFF


@dataclass(slots=True)
class ResidentEntry:
    """Metadata of one queued lookup result.

    ``exception`` records that the block carried an I-TLB exception. The queue
    latches one such entry and refuses further writes until a flush, because an
    exception must redirect before more speculative lookups are queued.
    """

    ptag: int
    vset_idx: int
    waymask: int
    maybe_rvc_map: int = 0
    exception: int = 0

    def copy(self) -> "ResidentEntry":
        return ResidentEntry(self.ptag, self.vset_idx, self.waymask,
                             self.maybe_rvc_map, self.exception)


@dataclass(frozen=True, slots=True)
class Refill:
    """A miss response completing this cycle, as seen by the memo."""

    blk_paddr: int
    waymask: int
    maybe_rvc_map: int = 0
    corrupt: int = 0


@dataclass(frozen=True, slots=True)
class PointerState:
    """Pointer and residency state after an accepted clock edge."""

    read: int = 0
    write: int = 0
    tail_ftq_flag: int = 0
    tail_ftq_value: int = 0
    exception_valid: int = 0
    exception_ptr: int = 0


@dataclass(frozen=True, slots=True)
class CycleResult:
    """Values the RTL presents during the cycle *before* this edge."""

    empty: int
    write_ready: int
    read_valid: int
    read_second_valid: int
    read_index: int
    read_second_index: int
    occupancy: int
    state: PointerState


class WayLookupModel:
    """Cycle-accurate residency model; one call per clock edge."""

    def __init__(self, depth: int = 32, fetch_ports: int = FETCH_PORTS) -> None:
        if depth <= 0:
            raise ValueError("prefetch depth must be positive")
        if fetch_ports not in (1, 2):
            raise ValueError("only one or two fetch ports are supported")
        self.depth = depth
        self.fetch_ports = fetch_ports
        self.modulus = 2 * depth
        self.state = PointerState()
        # FIFO order is what the main pipe observes; slot storage is only
        # needed for the metadata-update rule, which addresses entries by slot.
        # ``order[0]`` is the entry at the read pointer; slot addressing is
        # derived from the read pointer so there is only one copy of each memo.
        self.order: list[ResidentEntry] = []

    # -- derived quantities -------------------------------------------------
    def occupancy(self, state: PointerState | None = None) -> int:
        state = state or self.state
        return (state.write - state.read) % self.modulus

    def empty(self, state: PointerState | None = None) -> int:
        return int(self.occupancy(state) == 0)

    def write_ready(self, state: PointerState | None = None) -> int:
        state = state or self.state
        free = self.depth - self.occupancy(state)
        return int(free >= self.fetch_ports and not state.exception_valid)

    def read_valid(self, *, flush: int = 0, update_slots: tuple[bool, ...] = (False, False),
                   state: PointerState | None = None) -> int:
        state = state or self.state
        return int(not self.empty(state) and not update_slots[0] and not flush)

    def second_read_valid(self, *, flush: int = 0,
                          update_slots: tuple[bool, ...] = (False, False),
                          state: PointerState | None = None) -> int:
        state = state or self.state
        return int(self.occupancy(state) > 1 and not update_slots[0] and not update_slots[1]
                   and not flush)

    def write_index(self, state: PointerState | None = None) -> int:
        """Slot the next accepted write will land in."""
        state = state or self.state
        return state.write % self.depth

    def read_index(self, slot: int = 0, state: PointerState | None = None) -> int:
        state = state or self.state
        return (state.read + slot) % self.depth

    # -- residency queries --------------------------------------------------
    @property
    def tags(self) -> list[int]:
        return [entry.ptag for entry in self.order]

    def head(self) -> ResidentEntry | None:
        return self.order[0] if self.order else None

    def peek(self, count: int) -> list[ResidentEntry]:
        return self.order[:count]

    # -- cycle step ---------------------------------------------------------
    def step(
        self,
        *,
        flush: int = 0,
        s3_flush_valid: int = 0,
        s3_flush_ftq: int = 0,
        write_fire: int = 0,
        write_entries: tuple[ResidentEntry, ...] = (),
        write_ftq_flag: int = 0,
        write_ftq_value: int = 0,
        deq: int = 0,
        refills: tuple[Refill, ...] = (),
    ) -> CycleResult:
        """Advance one edge and return the values sampled at its start.

        ``deq`` is how many entries the main pipe accepted (0..2).
        ``write_fire`` is how many prefetch ports completed a handshake.
        ``refills`` are miss responses completing this cycle; an entry they
        rewrite cannot be read.
        """
        if deq not in (0, 1, 2):
            raise ValueError(f"dequeue count must be 0..2, got {deq}")
        if write_fire not in (0, 1, 2):
            raise ValueError(f"write count must be 0..2, got {write_fire}")
        if write_fire and len(write_entries) != write_fire:
            raise ValueError("write_entries must describe every accepted write")
        if write_fire == 2 and self.fetch_ports == 1:
            raise ValueError("single-port DUT cannot accept two writes")

        before = self.state
        updated_slots = self.updated_slots(before, refills)
        result = CycleResult(
            empty=self.empty(before),
            write_ready=self.write_ready(before),
            read_valid=self.read_valid(flush=flush, update_slots=updated_slots, state=before),
            read_second_valid=self.second_read_valid(
                flush=flush, update_slots=updated_slots, state=before),
            read_index=self.read_index(0, before),
            read_second_index=self.read_index(1, before),
            occupancy=self.occupancy(before),
            state=before,
        )

        # A refill completing this cycle rewrites the memo of every entry it
        # touches, before the pointer update is applied.
        self.apply_updates(refills)

        s3_drop = int(
            bool(s3_flush_valid) and not self.empty(before)
            and self._not_after(s3_flush_ftq, before)
        )

        if flush:
            read = 0
            write = 0
            tail_flag = 0
            tail_value = 0
        else:
            read = (before.read + deq) % self.modulus
            if s3_drop:
                write = (before.write - 1) % self.modulus
            elif write_fire:
                write = (before.write + write_fire) % self.modulus
            else:
                write = before.write
            tail_flag = write_ftq_flag if write_fire else before.tail_ftq_flag
            tail_value = write_ftq_value if write_fire else before.tail_ftq_value

        exception_valid = before.exception_valid
        exception_ptr = before.exception_ptr
        if flush or (s3_drop and before.exception_ptr == (before.write - 1) % self.depth):
            exception_valid = 0
        # Only a write that survives can latch its exception.  A write cancelled
        # by the flush (or by the stage-3 drop, which takes the write pointer)
        # never becomes an entry, so it must not leave an exception pointer
        # behind: the queue would then be empty yet refuse every write.
        if write_fire and not flush and not s3_drop and write_entries[0].exception:
            exception_valid = 1
            exception_ptr = before.write % self.depth

        self.state = PointerState(
            read=read,
            write=write,
            tail_ftq_flag=tail_flag,
            tail_ftq_value=tail_value,
            exception_valid=exception_valid,
            exception_ptr=exception_ptr,
        )

        if flush:
            self.order.clear()
        else:
            if deq:
                if deq > len(self.order):
                    raise AssertionError(
                        f"model cannot dequeue {deq} from {len(self.order)} resident")
                del self.order[:deq]
            if s3_drop and self.order:
                self.order.pop()
            elif write_fire:
                self.order.extend(entry.copy() for entry in write_entries)
        return result

    # -- helpers ------------------------------------------------------------
    def updated_slots(self, state: PointerState, refills: tuple[Refill, ...],
                      slots: int = 2) -> tuple[bool, ...]:
        """Which read slots have their metadata rewritten on this edge."""
        if not refills:
            return (False,) * slots
        return tuple(
            offset < len(self.order) and self._slot_touched(self.order[offset], refills)
            for offset in range(slots)
        )

    def apply_updates(self, refills: tuple[Refill, ...]) -> list[int]:
        """Apply refill metadata to resident memos; return the touched slots.

        A memo is rewritten in place so the FIFO order and every reader see the
        corrected metadata.
        """
        touched: list[int] = []
        for offset, entry in enumerate(self.order):
            updated = entry
            for refill in refills:
                if refill.corrupt:
                    continue
                new = self.refill_result(updated, refill)
                if new is not None:
                    updated = new
                    if offset not in touched:
                        touched.append(offset)
            if updated is not entry:
                self.order[offset] = updated
        return touched

    @staticmethod
    def _slot_touched(entry: ResidentEntry | None, refills: tuple[Refill, ...]) -> bool:
        if entry is None:
            return False
        return any(
            not refill.corrupt and WayLookupModel.refill_result(entry, refill) is not None
            for refill in refills
        )

    def note_write(self, ftq_value: int, ftq_flag: int = 0) -> None:
        """Record the FTQ index of the youngest entry after a write cycle."""
        self.state = PointerState(
            read=self.state.read,
            write=self.state.write,
            tail_ftq_flag=ftq_flag,
            tail_ftq_value=ftq_value,
        )

    # -- refill-update rule -------------------------------------------------
    @staticmethod
    def refill_result(entry: ResidentEntry, refill: Refill) -> ResidentEntry | None:
        """New metadata for ``entry`` after a refill, or ``None`` if unchanged.

        Rule (cache-ownership, applied to a speculative lookup memo):

        * different set             -> unrelated, unchanged
        * same set and same tag     -> adopt the filled way and RVC map
        * same set, identical waymask -> the memoised way now holds another
                                       line, so the memo no longer owns it:
                                       invalidate
        * same set, other waymask   -> unrelated, unchanged

        The way claim is compared for *equality*, not overlap: a refill fills
        exactly one way, and the memo's kept waymask is likewise one-hot. Only
        an exact match proves the memo's claim was overwritten.
        
        """
        if entry.vset_idx != idx_from_block(refill.blk_paddr):
            return None
        if ptag_from_block(refill.blk_paddr) == entry.ptag:
            return ResidentEntry(entry.ptag, entry.vset_idx, refill.waymask,
                                 refill.maybe_rvc_map, entry.exception)
        if entry.waymask != 0 and entry.waymask == refill.waymask:
            return ResidentEntry(entry.ptag, entry.vset_idx, 0,
                                 entry.maybe_rvc_map, entry.exception)
        return None

    def _not_after(self, s3_ftq: int, state: PointerState) -> bool:
        """``!isAfter(s3, tailFtqIdx)`` in the FTQ pointer space."""
        tail = (state.tail_ftq_flag << 6) | (state.tail_ftq_value & (FTQ_ENTRIES - 1))
        return (s3_ftq & (2 * FTQ_ENTRIES - 1)) <= tail
