"""Cycle agent for the IBuffer top level.

Tests submit semantic ``Beat`` objects (an ordered fetch beat plus backend
controls).  The agent places the beat at the IFU write-bank alignment lane
derived from the model's enqueue pointer, announces each beat one cycle ahead
through ``prevInstrCount`` as the IFU does, and compares the full output
surface on both phases of every edge.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import replace

from toffee import Execution, XCommClockBackend

from suites.frontend.ibuffer.testbenches.shared.env.driver.slot import ExplicitSlotDriver
from suites.frontend.ibuffer.testbenches.ibuffer.model import Beat
from suites.frontend.ibuffer.testbenches.ibuffer.model import IBufferModel
from suites.frontend.ibuffer.testbenches.ibuffer.model import Inputs
from suites.frontend.ibuffer.testbenches.ibuffer.model import StimulusError

from suites.frontend.ibuffer.testbenches.ibuffer.checker import check_outputs
from suites.frontend.ibuffer.testbenches.ibuffer.checker import check_reset
from suites.frontend.ibuffer.testbenches.ibuffer.env.ports import INTERFACE
from suites.frontend.ibuffer.testbenches.ibuffer.env.ports import IBufferPorts
from suites.frontend.ibuffer.testbenches.ibuffer.transactions import CheckedCycle


class IBufferAgent:
    def __init__(self, harness):
        self.dut = harness.dut  # Native coverage discovery, never a test API.
        self.interface = INTERFACE
        self._ports = IBufferPorts(self.dut)
        self._driver = ExplicitSlotDriver(
            self.dut.clock, self._ports.bits,
            idle=self._ports.encode(Inputs()),
            encoder=self._ports.encode,
            name="ibuffer.top.inputs",
        )
        self._monitor = None
        self._model = IBufferModel()
        self._used = self._busy = self._finished = self._failed = False
        self._reset_done = False
        self._last_tick = None
        self._announced = 0
        self.checked_cycles = 0

    # -- lifecycle ----------------------------------------------------------
    @asynccontextmanager
    async def running(self):
        if self._used:
            raise RuntimeError("IBuffer agent cannot be restarted")
        self._used = True
        from suites.frontend.ibuffer.testbenches.shared.env.monitor.cycle import DualPhaseMonitor
        monitor = DualPhaseMonitor(self.dut.clock, self._ports.capture, self._ports.capture)
        backend = XCommClockBackend(self.dut.GetXClock())
        try:
            async with Execution(backend) as execution:
                async with self._driver.holding(execution), monitor.running(execution):
                    self._monitor = monitor
                    try:
                        yield self
                        await self.finish()
                    finally:
                        self._monitor = None
        finally:
            backend.close()

    def _enter_work(self):
        if self._monitor is None:
            raise RuntimeError("IBuffer requires its fixture-managed Execution")
        if self._finished:
            raise RuntimeError("IBuffer input stream is finished")
        if self._failed:
            raise RuntimeError("IBuffer has an unreconciled slot after failure")
        if self._busy:
            raise RuntimeError("concurrent IBuffer operations are not supported")
        self._busy = True

    async def _exchange(self, inputs: Inputs):
        edge = await self._driver.send(inputs)
        before, after = await self._monitor.recv()
        assert before.event.tick + 1 == edge.tick == after.event.tick, (
            "IBuffer stale or missing phase snapshot")
        if self._last_tick is not None:
            assert edge.tick == self._last_tick + 2, (
                "IBuffer skipped or repeated an input slot")
        self._last_tick = edge.tick
        return before, after

    async def _cycle_locked(self, inputs: Inputs) -> CheckedCycle:
        if not isinstance(inputs, Inputs):
            raise TypeError("IBuffer requires semantic Inputs")
        try:
            expected_before = self._model.outputs(inputs)
            events = self._model.events(inputs)
            state_before = self._model.snapshot()
            before, after = await self._exchange(inputs)
            self._model.tick(inputs)
            expected_after = self._model.outputs(inputs)
            state_after = self._model.snapshot()
            if inputs.reset:
                check_reset(before.value, phase="before")
                check_reset(after.value, phase="after")
            else:
                check_outputs(expected_before, before.value, phase="before")
                check_outputs(expected_after, after.value, phase="after")
            self.checked_cycles += 1
            return CheckedCycle(self.checked_cycles, before.event.tick, after.event.tick,
                                inputs, before.value, after.value, expected_before,
                                expected_after, events, state_before, state_after)
        except BaseException:
            self._failed = True
            raise

    # -- public operations --------------------------------------------------
    async def reset(self, cycles: int = 3) -> None:
        if not isinstance(cycles, int) or cycles < 1:
            raise ValueError("reset requires a positive cycle budget")
        self._enter_work()
        try:
            for _ in range(cycles):
                await self._cycle_locked(Inputs(reset=1))
            self._reset_done = True
            self._announced = 0
            await self._cycle_locked(Inputs())
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    @property
    def model(self) -> IBufferModel:
        return self._model

    @property
    def occupancy(self) -> int:
        return (self._model.enq_ptr - self._model.deq_ptr[0]) % 48

    @property
    def next_lane_offset(self) -> int:
        return self._model.enq_ptr % 4

    @property
    def cycle_count(self) -> int:
        return self.checked_cycles

    def snapshot(self) -> dict[str, object]:
        return self._model.snapshot()

    def audit(self) -> dict:
        return {
            "top": "IBuffer",
            "inputs": sorted(INTERFACE["inputs"]),
            "outputs": sorted(INTERFACE["outputs"]),
            "not_compared": dict(INTERFACE["not_compared"]),
            "vtype_gen": "the real VTypeGen submodule is retained in the closure",
            "staging": "8-entry output window; head-contiguous by contract",
        }

    async def cycle(self, inputs: Inputs, *, announce: int = 0) -> CheckedCycle:
        """Drive one already-encoded cycle.

        ``announce`` is the ``prevInstrCount`` promise for the *next* cycle.
        A beat may only enqueue up to the previously announced count; use
        :meth:`play` for multi-beat flows, which announces exactly.
        """
        if not self._reset_done:
            raise RuntimeError("IBuffer requires an explicit reset before input")
        if not isinstance(inputs, Inputs):
            raise TypeError("IBuffer requires semantic Inputs")
        if not isinstance(announce, int) or not 0 <= announce < 64:
            raise ValueError("announce must fit prevInstrCount")
        count = bin(inputs.enq_enable).count("1")
        if count > self._announced:
            raise StimulusError(
                f"beat enqueues {count} instructions but only "
                f"{self._announced} were announced")
        inputs = replace(inputs, prev_instr_count=announce)
        self._enter_work()
        try:
            result = await self._cycle_locked(inputs)
            self._announced = announce
            return result
        finally:
            self._busy = False

    async def play(self, beats) -> list[CheckedCycle]:
        """Drive a sequence of semantic beats with exact IFU announcement."""
        if not self._reset_done:
            raise RuntimeError("IBuffer requires an explicit reset before input")
        beats = list(beats)
        for beat in beats:
            if not isinstance(beat, Beat):
                raise TypeError("play requires semantic Beat objects")
        if not beats:
            return []
        announcements = [beats[index + 1].count if index + 1 < len(beats) else 0
                         for index in range(len(beats))]
        cycles: list[CheckedCycle] = []
        # The IFU announces the first beat during the preceding idle cycle.
        if beats[0].count > self._announced:
            self._enter_work()
            try:
                await self._cycle_locked(Inputs(prev_instr_count=beats[0].count))
                self._announced = beats[0].count
            finally:
                self._busy = False
        for index, beat in enumerate(beats):
            offset = self._model.enq_ptr % 4
            inputs = beat.to_inputs(offset, prev_instr_count=announcements[index])
            self._enter_work()
            try:
                cycles.append(await self._cycle_locked(inputs))
                self._announced = announcements[index]
            finally:
                self._busy = False
        return cycles

    async def idle(self, **controls) -> CheckedCycle:
        return await self.cycle(Beat(in_valid=0, **controls).to_inputs(0),
                                announce=0)

    async def flush(self) -> CheckedCycle:
        return await self.cycle(Beat(in_valid=0, flush=1).to_inputs(0), announce=0)

    async def finish(self, max_cycles: int = 1) -> None:
        if self._finished:
            return
        if not isinstance(max_cycles, int) or max_cycles < 1:
            raise ValueError("finish requires a positive cycle budget")
        self._enter_work()
        try:
            if not self._reset_done:
                raise RuntimeError("IBuffer requires an explicit reset before finish")
            for _ in range(max_cycles):
                await self._cycle_locked(Inputs())
            self._finished = True
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False
