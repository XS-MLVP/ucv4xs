"""Reference model for ICacheMshr (a one-entry miss status holding register).

Semantics are the standard non-blocking-cache MSHR contract, not the RTL body:

* **Allocation** - an MSHR holds at most one outstanding block request. It
  advertises ready only while free, so the fetch pipeline cannot launch a second
  miss before the first is serviced (Hennessy & Patterson, "Computer
  Architecture: A Quantitative Approach", non-blocking cache / MSHR chapter;
  also the miss-handling section of the RISC-V platform-level cache guidance).
* **Secondary lookup** - while the entry is live, any lookup naming the same
  physical block *and* the same cache set hits. The set index is part of the
  identity because the same physical block can be mapped by different virtual
  sets (VIPT aliasing), so a set mismatch must not be reported as a hit.
* **Victim capture** - the replacement way is sampled when the memory request is
  actually issued, not at allocation: the replacer's answer is only meaningful
  for the cycle in which the line is fetched.
* **Bypass information** - the live entry publishes block, set and captured way
  so the refill path can write the SRAM and answer the waiting fetches. That
  publication stops as soon as the entry stops being usable (flush or fence.i).
* **Flush and fence.i** - both invalidate the entry. If the request has not been
  issued yet, it can be dropped immediately (nothing is outstanding). If it has
  been issued, the entry must stay live until the response arrives so the
  outstanding transaction is not lost, but it must no longer report hits or
  publish bypass information.
* **Completion** - the miss unit signals completion after it has consumed the
  information; the entry then frees itself.
* **WFI** - it is only safe to enter WFI when no issued request is outstanding.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MshrState:
    valid: int = 0
    issued: int = 0
    draining: int = 0        # flushed after issue, waiting for the response
    blk_paddr: int = 0
    vset_idx: int = 0
    way: int = 0

    @property
    def issue_way(self) -> int:
        return self.way


@dataclass(frozen=True, slots=True)
class Outputs:
    """Combinational view of the DUT for one state and one stimulus set."""

    req_ready: int
    acquire_valid: int
    info_valid: int
    info_block: int
    info_way: int
    hit: tuple[int, ...]
    wfi_safe: int


@dataclass(frozen=True, slots=True)
class CycleResult:
    """Values the DUT presents during the cycle before this edge."""

    req_ready: int
    acquire_valid: int
    acquire_block: int
    info_valid: int
    info_block: int
    info_way: int
    hit: tuple[int, int]
    wfi_safe: int
    state: MshrState


class MshrModel:
    """One-entry MSHR; one call per clock edge."""

    def __init__(self) -> None:
        self.state = MshrState()

    # -- derived -----------------------------------------------------------
    def req_ready(self, *, fencei: int = 0, state: MshrState | None = None) -> int:
        """A free entry still refuses a new block while a fence.i is in flight."""
        state = state or self.state
        return int(not state.valid and not fencei)

    def acquire_valid(self, *, fencei: int = 0, wfi_req: int = 0,
                      state: MshrState | None = None) -> int:
        state = state or self.state
        return int(state.valid and not state.issued and not fencei and not wfi_req)

    def hit(self, blk_paddr: int, vset_idx: int, *, fencei: int = 0,
            state: MshrState | None = None) -> int:
        state = state or self.state
        return int(bool(state.valid) and not fencei and not state.draining
                   and state.blk_paddr == blk_paddr and state.vset_idx == vset_idx)

    def info_valid(self, *, fencei: int = 0, state: MshrState | None = None) -> int:
        state = state or self.state
        return int(bool(state.valid) and not fencei and not state.draining)

    def wfi_safe(self, state: MshrState | None = None) -> int:
        state = state or self.state
        return int(not (state.valid and state.issued))

    def outputs(self, *, fencei: int = 0, wfi_req: int = 0,
                lookups: tuple[tuple[int, int], ...] = (),
                state: MshrState | None = None) -> "Outputs":
        """Combinational outputs for ``state`` under this cycle's stimulus."""
        state = state or self.state
        return Outputs(
            req_ready=self.req_ready(fencei=fencei, state=state),
            acquire_valid=self.acquire_valid(fencei=fencei, wfi_req=wfi_req, state=state),
            info_valid=self.info_valid(fencei=fencei, state=state),
            info_block=state.blk_paddr,
            info_way=state.way,
            hit=tuple(self.hit(block, vset, fencei=fencei, state=state)
                      for block, vset in lookups) if lookups else (0, 0),
            wfi_safe=self.wfi_safe(state),
        )

    # -- cycle step --------------------------------------------------------
    def step(
        self,
        *,
        req_valid: int = 0,
        req_block: int = 0,
        req_vset: int = 0,
        acquire_ready: int = 0,
        victim_way: int = 0,
        fencei: int = 0,
        invalid: int = 0,
        wfi_req: int = 0,
        lookups: tuple[tuple[int, int], ...] = (),
    ) -> CycleResult:
        before = self.state
        result = CycleResult(
            req_ready=self.req_ready(fencei=fencei, state=before),
            acquire_valid=self.acquire_valid(fencei=fencei, wfi_req=wfi_req, state=before),
            acquire_block=before.blk_paddr,
            info_valid=self.info_valid(fencei=fencei, state=before),
            info_block=before.blk_paddr,
            info_way=before.way,
            hit=tuple(self.hit(block, vset, fencei=fencei, state=before)
                      for block, vset in lookups) if lookups else (0, 0),
            wfi_safe=self.wfi_safe(before),
            state=before,
        )

        valid, issued, draining = before.valid, before.issued, before.draining
        blk, vset, way = before.blk_paddr, before.vset_idx, before.way

        # Priority, highest first: completion, issue, allocation, flush. The
        # first three are mutually exclusive by construction (only a live entry
        # can complete or issue, only a free entry can allocate), so this order
        # only matters for flush colliding with the others.
        if invalid:
            valid, issued, draining = 0, 0, 0

        if valid and not issued and not fencei and not wfi_req and acquire_ready:
            # The replacement way is sampled on the edge that issues the fetch.
            issued = 1
            way = victim_way

        if req_valid and not valid:
            valid, issued, draining = 1, 0, 0
            blk, vset, way = req_block, req_vset, 0
        elif fencei and valid and not issued:
            # An unissued request can be dropped; an issued one must drain.
            valid, issued, draining = 0, 0, 0
        elif fencei and valid and issued:
            draining = 1

        self.state = MshrState(valid=valid, issued=issued, draining=draining,
                               blk_paddr=blk, vset_idx=vset, way=way)
        return result

    # -- helpers -----------------------------------------------------------
    def expect(self, *, ready: int | None = None, info_valid: int | None = None,
               acquire_valid: int | None = None, wfi_safe: int | None = None) -> None:
        checks = (
            ("req.ready", ready, self.req_ready()),
            ("info.valid", info_valid, self.info_valid()),
            ("acquire.valid", acquire_valid, self.acquire_valid()),
            ("wfi.safe", wfi_safe, self.wfi_safe()),
        )
        for name, expected, actual in checks:
            if expected is not None and expected != actual:
                raise AssertionError(f"{name}: DUT {expected} != model {actual}")
