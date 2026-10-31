"""Reference model for ICacheMissUnit.

Semantics come from the module's documented architecture (the priority diagram in
``ICacheMissUnit.scala`` and the standard non-blocking-cache MSHR discipline),
not from the RTL body:

* **Two MSHR pools** - four fetch MSHRs and ten prefetch MSHRs. A fetch request
  may only occupy a fetch MSHR and a prefetch request only a prefetch MSHR, so a
  prefetch storm can never consume the fetch pool (fetch is the latency-critical
  path).
* **Lowest free index wins** - within a pool the request goes to the lowest
  numbered free entry. With identical entries this is observationally the same
  as any allocation order, but it is what makes the acquire arbitration
  priority meaningful.
* **Duplicate suppression** - a request for a block/set pair already tracked by
  *any* MSHR is accepted (ready asserted) but allocates nothing. A prefetch that
  names the same block as the fetch request in the same cycle is also a
  duplicate, because the fetch will allocate it.
* **Acquire arbitration** - fetch MSHRs have priority over prefetch MSHRs: fetch
  is the architecturally critical path. Inside the fetch pool the lowest index
  wins. The prefetch pool is *not* served by index but in arrival order: the
  module keeps a FIFO of allocated prefetch entries and serves its head, so an
  older prefetch cannot be starved by a younger one.
* **Victim request** - the replacement way is requested from the replacer in the
  same cycle the acquire fires, for that MSHR's set.
* **Refill completion** - the response carries the entry's block, set and the
  one-hot mask of the victim way that was captured at issue time. A corrupt or
  denied refill must still be reported to the pipeline so the fetch can raise an
  access fault, but must never be written into the cache.
* **Flush semantics differ by pool** - ``flush`` (pipeline redirect) only affects
  prefetch entries, because a fetch miss is on the architectural path and must
  stay outstanding. ``fence.i`` affects both pools. An entry that already owns a
  memory transaction is never dropped early (the transaction must not leak);
  instead it completes silently: no response is published and no array write
  happens, because a line fetched before ``fence.i`` may be stale.
* **WFI safety** - safe only when no entry has an issued request outstanding. A
  pending WFI request blocks issuing a new acquire.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace


NUM_FETCH_MSHR = 4
NUM_PREFETCH_MSHR = 10


@dataclass
class Entry:
    """One MSHR."""

    is_fetch: bool
    valid: int = 0
    issued: int = 0
    blk_paddr: int = 0
    vset_idx: int = 0
    way: int = 0
    arrival: int = 0        # allocation order, used for prefetch arbitration
    flush_flag: int = 0     # a redirect arrived while this entry was live
    fencei_flag: int = 0    # fence.i arrived while this entry was live


@dataclass(frozen=True, slots=True)
class CycleResult:
    """Values the DUT presents during the cycle before this edge."""

    fetch_ready: int
    prefetch_ready: int
    acquire_valid: int
    acquire_source: int | None
    acquire_block: int
    acquire_vset: int
    victim_valid: int
    victim_vset: int
    resp_valid: int
    wfi_safe: int


@dataclass(frozen=True, slots=True)
class Response:
    """What the DUT must publish when a refill completes."""

    source: int
    valid: int
    block: int
    vset: int
    waymask: int
    corrupt: int
    denied: int
    meta_write: int
    data_write: int


class MissUnitModel:
    """Fourteen MSHRs (four fetch, ten prefetch); one call per clock edge."""

    def __init__(self, fetch_mshrs: int = NUM_FETCH_MSHR,
                 prefetch_mshrs: int = NUM_PREFETCH_MSHR) -> None:
        if fetch_mshrs <= 0 or prefetch_mshrs <= 0:
            raise ValueError("both MSHR pools must be non-empty")
        self.fetch_mshrs = fetch_mshrs
        self.prefetch_mshrs = prefetch_mshrs
        self.entries: list[Entry] = [
            Entry(is_fetch=index < fetch_mshrs)
            for index in range(fetch_mshrs + prefetch_mshrs)
        ]
        # Prefetch arrival order: indices in the order they were allocated.
        self.prefetch_order: list[int] = []
        self.arrival_counter = 0

    # -- pool helpers -------------------------------------------------------
    def fetch_pool(self) -> list[int]:
        return list(range(self.fetch_mshrs))

    def prefetch_pool(self) -> list[int]:
        return list(range(self.fetch_mshrs, len(self.entries)))

    def entry(self, index: int) -> Entry:
        return self.entries[index]

    def occupied(self) -> list[int]:
        return [index for index, entry in enumerate(self.entries) if entry.valid]

    # -- lookups ------------------------------------------------------------
    def hits(self, blk_paddr: int, vset_idx: int) -> bool:
        return any(
            entry.valid and entry.blk_paddr == blk_paddr and entry.vset_idx == vset_idx
            for entry in self.entries
        )

    def fetch_ready(self) -> int:
        """Ready while a fetch MSHR is free; a duplicate is also accepted."""
        return int(any(not self.entries[index].valid for index in self.fetch_pool()))

    def prefetch_ready(self) -> int:
        return int(any(not self.entries[index].valid for index in self.prefetch_pool()))

    def acquire_select(self) -> int | None:
        """Which MSHR owns the memory channel, honouring the documented order."""
        for index in self.fetch_pool():
            entry = self.entries[index]
            if entry.valid and not entry.issued:
                return index
        for index in list(self.prefetch_order):
            entry = self.entries[index]
            if entry.valid and not entry.issued:
                return index
        return None

    def wfi_safe(self) -> int:
        return int(not any(entry.valid and entry.issued for entry in self.entries))

    def pending(self) -> list[int]:
        return [index for index, entry in enumerate(self.entries)
                if entry.valid and not entry.issued]

    # -- cycle step ---------------------------------------------------------
    def step(
        self,
        *,
        fetch_valid: int = 0,
        fetch_block: int = 0,
        fetch_vset: int = 0,
        prefetch_valid: int = 0,
        prefetch_block: int = 0,
        prefetch_vset: int = 0,
        acquire_ready: int = 0,
        victim_way: int = 0,
        fencei: int = 0,
        flush: int = 0,
    ) -> CycleResult:
        """Advance one edge.

        The returned ``CycleResult`` describes the state the DUT presents during
        the cycle that *ends* at this edge, so it can be compared with values
        sampled before the edge.
        """
        selected_before = self.acquire_select()
        result = CycleResult(
            fetch_ready=self.fetch_ready(),
            prefetch_ready=self.prefetch_ready(),
            acquire_valid=int(selected_before is not None),
            acquire_source=selected_before,
            acquire_block=(self.entries[selected_before].blk_paddr
                           if selected_before is not None else 0),
            acquire_vset=(self.entries[selected_before].vset_idx
                          if selected_before is not None else 0),
            victim_valid=int(selected_before is not None),
            victim_vset=(self.entries[selected_before].vset_idx
                         if selected_before is not None else 0),
            resp_valid=0,
            wfi_safe=self.wfi_safe(),
        )

        # 1. Redirect / fence.i state. Issued entries are kept alive so their
        #    memory transaction cannot leak; unissued entries simply disappear.
        if fencei or flush:
            for index, entry in enumerate(self.entries):
                if not entry.valid:
                    continue
                if fencei:
                    entry.fencei_flag = 1
                elif entry.is_fetch:
                    # A redirect never touches the architecturally critical pool.
                    continue
                else:
                    entry.flush_flag = 1
                if not entry.issued:
                    entry.valid = 0
                    if index in self.prefetch_order:
                        self.prefetch_order.remove(index)

        # 2. Issue: at most one MSHR owns the memory channel per cycle.
        selected = self.acquire_select()
        if selected is not None and acquire_ready:
            entry = self.entries[selected]
            entry.issued = 1
            entry.way = victim_way
            if not entry.is_fetch and selected in self.prefetch_order:
                self.prefetch_order.remove(selected)

        # 3. Allocation into the lowest free index of the matching pool.
        if fetch_valid and not self.hits(fetch_block, fetch_vset):
            for index in self.fetch_pool():
                entry = self.entries[index]
                if not entry.valid:
                    entry.valid = 1
                    entry.issued = 0
                    entry.flush_flag = 0
                    entry.fencei_flag = 0
                    entry.blk_paddr = fetch_block
                    entry.vset_idx = fetch_vset
                    entry.arrival = self.arrival_counter
                    self.arrival_counter += 1
                    break

        # A prefetch naming this cycle's fetch block is a duplicate: the fetch
        # already covers it, so the prefetch must not allocate.
        same_cycle_dup = (fetch_valid and prefetch_valid
                          and fetch_block == prefetch_block
                          and fetch_vset == prefetch_vset)
        if prefetch_valid and not same_cycle_dup and not self.hits(prefetch_block,
                                                                  prefetch_vset):
            for index in self.prefetch_pool():
                entry = self.entries[index]
                if not entry.valid:
                    entry.valid = 1
                    entry.issued = 0
                    entry.flush_flag = 0
                    entry.fencei_flag = 0
                    entry.blk_paddr = prefetch_block
                    entry.vset_idx = prefetch_vset
                    entry.arrival = self.arrival_counter
                    self.arrival_counter += 1
                    self.prefetch_order.append(index)
                    break
        return result

    # -- refill completion --------------------------------------------------
    def complete(self, source: int, *, corrupt: int = 0, denied: int = 0) -> Response:
        """Finish the refill of ``source`` and return the required response.

        A redirect that arrived while the entry was live suppresses the response
        entirely (the pipeline has moved on) and, like a corrupt or denied line,
        prevents the arrays from being written.
        """
        entry = self.entries[source]
        if not entry.valid or not entry.issued:
            raise AssertionError(f"MSHR {source} is not awaiting a refill")
        # TileLink requires ``corrupt`` whenever ``denied`` is raised; tests give
        # the peer a consistent line, and the model follows the same contract.
        effective_corrupt = corrupt or denied
        suppressed = entry.flush_flag or entry.fencei_flag
        published = int(not suppressed)
        write = int(published and not effective_corrupt and not denied)
        response = Response(
            source=source,
            valid=published,
            block=entry.blk_paddr,
            vset=entry.vset_idx,
            waymask=1 << entry.way,
            corrupt=effective_corrupt,
            denied=denied,
            meta_write=write,
            data_write=write,
        )
        entry.valid = 0
        entry.issued = 0
        entry.flush_flag = 0
        entry.fencei_flag = 0
        return response

    def abandon(self, source: int) -> None:
        """Drop an issued entry without a response (used by test setup only)."""
        entry = replace(self.entries[source], valid=0, issued=0)
        self.entries[source] = entry
