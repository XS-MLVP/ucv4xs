"""Toffee environment for SbufferData: drive public ports, compare a byte model.

Timing contract used here (verified against the generated RTL):
a request driven in the stable phase is captured at the next rising edge and
becomes visible at the following rising edge. The helper therefore checks
"no early visibility" at the capture edge and "exact match" at the commit edge.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace

from toffee import RisingEdge, SamplingMonitor, SyncSingleCycleDriver

from .coverage import SbufferDataCoverage
from .model import LANES, LINES, SbufferDataModel, WriteRequest
from .ports import SbufferDataPorts
from .transactions import Frame, Op


class SbufferDataEnv:
    def __init__(self, dut, coverage: SbufferDataCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.model = SbufferDataModel()
        self._ports = SbufferDataPorts(dut)
        self._driver = SyncSingleCycleDriver(dut.clock, self._ports.bits,
            idle=self._ports.encode(Frame()), encoder=self._ports.encode, name='sbuffer_data.inputs')
        self._monitor = None
        self._snapshot = None
        self._frame = Frame()
        self._pipeline_active = False
        self._last_tick = None
        self.transactions = 0
        self.checked_edges = 0

    # ------------------------------------------------------------------ clock
    @asynccontextmanager
    async def managed(self, execution):
        if self._monitor is not None:
            raise RuntimeError('SbufferData environment already running')
        monitor = SamplingMonitor(RisingEdge(self.dut.clock), capture=self._ports.capture)
        async with self._driver, monitor.start(execution):
            self._monitor = monitor
            try:
                yield
                assert not self._pipeline_active, 'SbufferData has an uncommitted input stage'
                if self._last_tick is not None:
                    assert execution.backend.tick == self._last_tick, 'unconsumed SbufferData clock work'
            finally:
                self._monitor = None

    async def _edge(self, *, reset=False) -> None:
        if self._monitor is None:
            raise RuntimeError('SbufferData transactions require execution(env)')
        frame = replace(self._frame, reset=reset)
        edge = await self._driver.send(frame)
        observation = await self._monitor.recv()
        assert observation.event.tick == edge.tick, 'stale SbufferData output snapshot'
        self._last_tick = edge.tick
        self._snapshot = observation.value
        self._pipeline_active = not reset and bool(
            (frame.op.writes and frame.writes_valid) or (frame.op.flush is not None and frame.flush_valid))
        self._frame = Frame()

    # ------------------------------------------------------------------ reads
    def read_masks(self, lines=None) -> dict[int, tuple[int, ...]]:
        selected = range(LINES) if lines is None else lines
        result = {}
        for line in selected:
            if self._snapshot is None:
                raise RuntimeError('SbufferData has no sampled observation yet')
            result[line] = self._snapshot.masks[line]
        return result

    # ------------------------------------------------------------------ check
    def check(self, context: str, lines=None) -> None:
        selected = list(range(LINES) if lines is None else lines)
        actual = self.read_masks(selected)
        for line in selected:
            for lane in range(LANES):
                got = actual[line][lane]
                want = self.model.mask[line][lane]
                if got != want:
                    raise AssertionError(
                        f"{context}: mask mismatch line={line} lane={lane} "
                        f"expected={want:#06x} actual={got:#06x}"
                    )
        for line in selected:
            for lane in range(LANES):
                known = self.model.known[line][lane]
                if not known:
                    continue
                expected_data = self.model.data[line][lane]
                for byte, got in enumerate(self._snapshot.data[line][lane]):
                    if not (known >> byte) & 1:
                        continue
                    want = expected_data[byte]
                    if got != want:
                        raise AssertionError(
                            f"{context}: data mismatch line={line} lane={lane} byte={byte} "
                            f"expected={want:#04x} actual={got:#04x}"
                        )
        self.checked_edges += 1

    # ------------------------------------------------------------------ drive
    def _drive_op(self, op: Op) -> None:
        frame = Frame(op)
        self._ports.encode(frame)
        self._frame = frame

    def _clear_pins(self) -> None:
        self._frame = Frame()

    def _commit(self, op: Op, context: str, lines=None) -> None:
        self.model.apply(op.writes, op.flush)
        self.check(context, lines)
        self.transactions += 1
        if self.coverage is not None:
            self.coverage.sample_op(op.writes, op.flush)

    # ------------------------------------------------------------------ cases
    async def reset(self, context: str = "reset_idle") -> None:
        await self._edge(reset=True)
        await self._edge(reset=True)
        self.model.reset()
        await self._edge()
        self.check("after reset")
        if self.coverage is not None:
            self.coverage.sample_reset(context)

    async def idle(self, cycles: int = 3, context: str = "after_write") -> None:
        for index in range(cycles):
            await self._edge()
            self.check(f"idle cycle {index}")
        if self.coverage is not None:
            self.coverage.sample_idle(context)

    async def burst(self, ops: tuple[Op, ...] | list[Op], lines_per_op=None) -> None:
        if not ops:
            raise ValueError("burst requires at least one op")
        if lines_per_op is not None and len(lines_per_op) != len(ops):
            raise ValueError("lines_per_op length differs from ops")
        for op in ops:
            self._ports.encode(Frame(op))
        self._drive_op(ops[0])
        for index, op in enumerate(ops):
            await self._edge()  # capture of op[index]; commit of op[index - 1]
            if index == 0:
                self.check("capture latency")
            else:
                lines = None if lines_per_op is None else lines_per_op[index - 1]
                self._commit(ops[index - 1], f"burst op {index - 1}", lines)
            if index + 1 < len(ops):
                self._drive_op(ops[index + 1])
            else:
                self._clear_pins()
        await self._edge()
        lines = None if lines_per_op is None else lines_per_op[-1]
        self._commit(ops[-1], f"burst op {len(ops) - 1}", lines)
        if lines_per_op is not None:
            self.check("burst end full check")

    async def issue(self, writes: tuple[WriteRequest, ...] = (), flush: int | None = None) -> None:
        await self.burst([Op(tuple(writes), flush)])

    async def invalid_write(self, req: WriteRequest) -> None:
        self._drive_op(Op((req,), None))
        self._frame = replace(self._frame, writes_valid=False)
        await self._edge()
        self.check("invalid write capture")
        await self._edge()
        self.check("invalid write commit")
        self._clear_pins()

    async def invalid_flush(self, wvec: int) -> None:
        self._frame = Frame(Op(flush=wvec), flush_valid=False)
        await self._edge()
        await self._edge()
        self.check("invalid flush")
        self._clear_pins()

    async def reset_pending_write(self, req: WriteRequest) -> None:
        self._drive_op(Op((req,), None))
        await self._edge()  # capture in s1
        self.check("pending write capture")
        self._clear_pins()
        await self._edge(reset=True)  # s2 would commit here, reset cancels it
        self.model.reset()
        await self._edge(reset=True)
        await self._edge()
        self.check("after reset cancels pending write")
        if self.coverage is not None:
            self.coverage.sample_reset("reset_pending_write")

    async def reset_with_flush(self, wvec: int) -> None:
        self._frame = Frame(Op(flush=wvec))
        await self._edge(reset=True)
        self._frame = Frame(Op(flush=wvec))
        await self._edge(reset=True)
        self.model.reset()
        self._clear_pins()
        await self._edge()
        self.check("after reset with flush")
        if self.coverage is not None:
            self.coverage.sample_reset("reset_with_flush")
