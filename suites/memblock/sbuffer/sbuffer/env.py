"""Toffee environment for the Sbuffer top level.

Only public ports are driven and observed. The reference tracks physical-tag
lines and merged bytes; the DUT's slot id is matched to a unique live line by
payload, so PLRU slot choice is not asserted while payload correctness is.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace

from toffee import DriveStable, SamplingMonitor

from .coverage import SbufferCoverage
from .checker import WritebackLedger
from .driver import SbufferDriver
from .model import LANES, Enq, SbufferModel, LANE_MASK
from .ports import SbufferPorts
from .transactions import Controls, Cycle, Writeback


class SbufferEnv:
    def __init__(self, dut, coverage: SbufferCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.model = SbufferModel()
        self.ledger = WritebackLedger(self.model)
        self._ports = SbufferPorts(dut)
        self._driver = SbufferDriver(self._ports)
        self._controls = Controls()
        self._monitor = None
        self._busy = False
        self.tick = 0

    # ------------------------------------------------------------------ basics
    @asynccontextmanager
    async def managed(self, execution):
        """One owner, lossless stable snapshots, strict accepted-work teardown.

        Resident lines are allowed for forwarding/capacity-only tests. Accepted
        DCache writes and replay retries must complete or be explicitly reset.
        """
        if self._monitor is not None:
            raise RuntimeError('Sbuffer environment already running')
        monitor = SamplingMonitor(DriveStable(self.dut.clock), capture=self._ports.capture)
        async with self._driver, monitor.start(execution):
            self._monitor = monitor
            try:
                yield
                if self.tick:
                    assert execution.backend.tick == self._last_tick, 'unconsumed clock work outside Sbuffer driver'
                self.ledger.finish()
            finally:
                self._monitor = None

    def configure(self, *, timeout_cycles=None, force_write=None):
        changes = {}
        if timeout_cycles is not None:
            changes['timeout'] = timeout_cycles
        if force_write is not None:
            changes['force_write'] = force_write
        controls = replace(self._controls, **changes)
        self._ports.encode(Cycle(controls=controls))
        self._controls = controls

    def set_store_path(self, *, sq_empty=None, misses_empty=None):
        changes = {}
        if sq_empty is not None:
            changes['sq_empty'] = sq_empty
        if misses_empty is not None:
            changes['misses_empty'] = misses_empty
        controls = replace(self._controls, **changes)
        self._ports.encode(Cycle(controls=controls))
        self._controls = controls

    def status(self):
        return self._ports.status()

    async def _cycle(self, **fields):
        if self._monitor is None:
            raise RuntimeError('Sbuffer transactions require execution(env)')
        if self._busy:
            raise RuntimeError('concurrent Sbuffer cycle calls are not supported')
        command = Cycle(controls=self._controls, **fields)
        self._ports.encode(command)
        self._busy = True
        try:
            edge = await self._driver.send(command)
            transfer = await self._monitor.recv()
            observed = transfer.value
            assert transfer.event.tick + 1 == edge.tick, 'missing or stale pre-edge snapshot'
            assert bool(observed.reset) == bool(command.reset)
            assert tuple((port, req) for port, req, _ in observed.enqueues) == command.enqueues, (
                'enqueue binding/encoding mismatch', command, observed)
            assert (observed.hit, observed.replay) == (command.hit, command.replay), (
                'response binding/encoding mismatch', command, observed)
            self.tick += 1
            self._last_tick = edge.tick
            # All channels come from the same stable snapshot, confirmed by its
            # rising edge. No API branch is allowed to skip simultaneous work.
            accepted = self.ledger.observe(observed, edge.tick)
            return observed, accepted
        finally:
            self._busy = False

    async def edge(self) -> None:
        await self._cycle()

    async def settle(self, cycles: int = 2) -> None:
        for _ in range(cycles):
            await self.edge()

    async def reset(self, context: str = "idle") -> None:
        await self._cycle(reset=True)
        await self._cycle(reset=True)
        await self.edge()
        status = self.status()
        assert status.empty, "sbempty must be 1 after reset"
        assert not status.full, "sbFull must be 0 after reset"
        assert not status.request_pending, "no dcache request after reset"
        if self.coverage is not None:
            self.coverage.sample_reset(context)

    # ------------------------------------------------------------------ enqueue
    async def enqueue(
        self, reqs: list[Enq], expect_ready=None, note: str = "", ports=None
    ) -> dict[int, int]:
        if len(reqs) > 2:
            raise ValueError("Sbuffer has two enqueue ports")
        if ports is None:
            ports = tuple(range(len(reqs)))
        if len(ports) != len(reqs):
            raise ValueError("ports and enqueue requests length differ")
        targets = [self.model.active_same_tag(req.ptag) for req in reqs]
        wanted = list(expect_ready) if expect_ready is not None else [1] * len(reqs)
        if len(wanted) != len(reqs) or any(value not in (0, 1) for value in wanted):
            raise ValueError('expect_ready must specify one boolean per offered request')
        observed, _ = await self._cycle(enqueues=tuple(zip(ports, reqs)))
        actual = {port: int(ready) for port, _, ready in observed.enqueues}
        accepted = [req for port, req in zip(ports, reqs) if actual[port]]
        assert [actual[port] for port in ports] == wanted, (
            f'{note}: ready {[actual[port] for port in ports]} != expected {wanted}')

        if self.coverage is not None:
            if not accepted:
                kind = "blocked_drain" if self.model.uarch_drain else "blocked_full"
                self.coverage.sample_enqueue(kind, [])
            elif len(accepted) == 2:
                kind = "same_cycle_same_tag" if accepted[0].ptag == accepted[1].ptag else "same_cycle_diff_tags"
                lanes = {accepted[0].lane, accepted[1].lane}
                self.coverage.sample_enqueue(kind, sorted(lanes))
                self.coverage.sample_capacity("not_full")
            else:
                req = accepted[0]
                target = targets[reqs.index(req)]
                if target is None:
                    kind = "new_line"
                elif target.vtag == req.vtag:
                    kind = "merge_same_vtag"
                else:
                    kind = "merge_diff_vtag"
                lanes = list(range(LANES)) if req.wline else [req.lane]
                inflight_same = any(
                    line.ptag == req.ptag and line.inflight for line in self.model.lines
                )
                self.coverage.sample_enqueue(kind, lanes)
                self.coverage.sample_capacity("not_full")
                if inflight_same:
                    self.coverage.sample_sameblock("allocate_while_inflight")
        return actual

    # ------------------------------------------------------------------ requests
    def read_req(self) -> Writeback:
        self.dut.RefreshComb()
        request = self._ports.request()
        assert request is not None, 'no currently offered writeback'
        return self.ledger.inspect(request)

    async def wait_req(
        self, note: str = "", max_cycles: int = 40, allow_inflight: bool = False
    ) -> Writeback:
        for _ in range(max_cycles):
            await self.edge()
            if self.status().request_pending:
                snap = self.read_req()
                return snap
        raise TimeoutError(f"{note}: no dcache request within {max_cycles} cycles")

    async def no_req_for(self, cycles: int, note: str = "") -> None:
        for _ in range(cycles):
            await self.edge()
            assert not self.status().request_pending, f"{note}: unexpected dcache request"

    async def accept(self, snap: Writeback, reason: str) -> Writeback:
        _, accepted = await self._cycle(accept_request=True)
        assert accepted is not None, 'writeback was not valid at its accepting edge'
        assert accepted == snap, ('stale offered writeback handle at acceptance', snap, accepted)
        if self.coverage is not None:
            lanes = [lane for lane in range(LANES) if (snap.mask >> (16 * lane)) & 0xFFFF]
            self.coverage.sample_request(reason, lanes or [0])
        return accepted

    async def hit(self, snap: Writeback) -> None:
        self.ledger.require_pending(snap)
        await self._cycle(hit=snap.id)

    async def replay(self, snap: Writeback) -> None:
        self.ledger.require_pending(snap)
        await self._cycle(replay=snap.id)
        if self.coverage is not None:
            self.coverage.sample_replay("replay_resp")

    # ------------------------------------------------------------------ forward
    async def forward(self, load_lane: int, vaddr: int, paddr: int, kill: bool = False):
        # Validate both stages before driving either one.
        self._ports.encode(Cycle(controls=self._controls, forward_s0=(load_lane, vaddr),
                                 forward_s1=(load_lane, paddr, kill)))
        await self._cycle(forward_s0=(load_lane, vaddr))
        await self._cycle(forward_s1=(load_lane, paddr, kill))
        response = self._ports.forward(load_lane)
        mask, data, invalid = response.mask, response.data, response.invalid
        expected_mask, expected_data, mismatch = self.model.forward(vaddr, paddr)
        lane = (paddr >> 4) & LANE_MASK
        if kill:
            assert invalid == 0, "kill must suppress matchInvalid"
        else:
            assert invalid == int(mismatch), (
                f"forward matchInvalid {invalid} != expected {int(mismatch)}"
            )
        assert mask == expected_mask, (
            f"forward mask {mask:#06x} != expected {expected_mask:#06x} (lane {lane})"
        )
        for byte in range(16):
            if (expected_mask >> byte) & 1:
                assert data[byte] == expected_data[byte], (
                    f"forward byte {byte} {data[byte]:#04x} != {expected_data[byte]:#04x}"
                )
        if self.coverage is not None:
            active = any(
                line.vtag == vaddr >> 6 and not line.inflight for line in self.model.lines
            )
            inflight = any(
                line.vtag == vaddr >> 6 and line.inflight for line in self.model.lines
            )
            if kill:
                result = "killed"
            elif mismatch and expected_mask:
                result = "mismatch_ptag"
            elif mismatch:
                result = "mismatch_vtag"
            elif expected_mask == 0:
                result = "no_match"
            elif active and inflight and any(
                newer.mask[lane] & older.mask[lane]
                for newer in self.model.lines if newer.vtag == vaddr >> 6 and not newer.inflight
                for older in self.model.lines if older.vtag == vaddr >> 6 and older.inflight
            ):
                result = "active_over_inflight"
            elif active:
                result = "active"
            else:
                result = "inflight"
            self.coverage.sample_forward(result, load_lane, lane)
        return response

    # ------------------------------------------------------------------ flush/drain
    async def start_flush(self, cmo: bool = False, sqempty: int = 1, mshr: int = 1) -> None:
        self.set_store_path(sq_empty=sqempty, misses_empty=mshr)
        self._controls = replace(self._controls, flush=True, cmo=cmo)
        await self.edge()

    async def end_flush(self):
        self._controls = replace(self._controls, flush=False, cmo=False)
        await self.edge()

    async def drain_requests(self, reason: str, max_cycles: int = 200, require_increasing: bool = True) -> list[Writeback]:
        if max_cycles < 1:
            raise ValueError('drain requires a positive cycle budget')
        drained = []
        last_id = -1
        deadline = self.tick + max_cycles
        while self.tick < deadline and self.model.lines:
            await self.edge()
            if self.status().request_pending:
                snap = self.read_req()
                if require_increasing:
                    assert snap.id > last_id, f"{reason}: drain ids not increasing: {snap.id} after {last_id}"
                    last_id = snap.id
                await self.accept(snap, reason)
                await self.hit(snap)
                drained.append(snap)
        if self.model.lines:
            raise TimeoutError(f'{reason}: drain budget exhausted with {len(self.model.lines)} live lines')
        self.ledger.finish()
        return drained

    async def flush_and_finish(
        self, cmo: bool = False, sqempty: int = 1, mshr: int = 1, expect_empty: bool = True
    ) -> list[Writeback]:
        await self.start_flush(cmo=cmo, sqempty=sqempty, mshr=mshr)
        drained = await self.drain_requests("drain_flush")
        await self.settle(3)
        if expect_empty:
            assert self.status().flush_complete, "flush.empty must be 1 after drain"
        if self.coverage is not None and self.status().flush_complete:
            self.coverage.sample_flush("cmo" if cmo else "normal", "normal_after_all")
        await self.end_flush()
        return drained

    async def drain_uarch(self) -> list[Writeback]:
        drained = await self.drain_requests('drain_uarch', max_cycles=100)
        await self.settle(3)
        if self.coverage is not None:
            self.coverage.sample_flush("uarch", "normal_after_all")
        self.model.uarch_drain = False
        return drained
