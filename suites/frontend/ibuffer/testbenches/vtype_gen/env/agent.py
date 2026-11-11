"""Cycle agent for the VTypeGen leaf DUT."""

from __future__ import annotations

from contextlib import asynccontextmanager

from toffee import Execution, XCommClockBackend

from suites.frontend.ibuffer.testbenches.shared.env.driver.slot import ExplicitSlotDriver
from suites.frontend.ibuffer.testbenches.vtype_gen.model import Inputs
from suites.frontend.ibuffer.testbenches.vtype_gen.model import VTypeGenModel

from suites.frontend.ibuffer.testbenches.vtype_gen.checker import check_outputs
from suites.frontend.ibuffer.testbenches.vtype_gen.env.ports import INTERFACE
from suites.frontend.ibuffer.testbenches.vtype_gen.env.ports import VTypeGenPorts
from suites.frontend.ibuffer.testbenches.vtype_gen.transactions import CheckedCycle


class VTypeGenAgent:
    def __init__(self, harness):
        self.dut = harness.dut  # Native coverage discovery, never a test API.
        self.interface = INTERFACE
        self._ports = VTypeGenPorts(self.dut)
        self._driver = ExplicitSlotDriver(
            self.dut.clock, self._ports.bits,
            idle=self._ports.encode(Inputs()),
            encoder=self._ports.encode,
            name="ibuffer.vtype_gen.inputs",
        )
        self._monitor = None
        self._model = VTypeGenModel()
        self._used = self._busy = self._finished = self._failed = False
        self._reset_done = False
        self._last_tick = None
        self.checked_cycles = 0

    # -- lifecycle ----------------------------------------------------------
    @asynccontextmanager
    async def running(self):
        if self._used:
            raise RuntimeError("VTypeGen agent cannot be restarted")
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
            raise RuntimeError("VTypeGen requires its fixture-managed Execution")
        if self._finished:
            raise RuntimeError("VTypeGen input stream is finished")
        if self._failed:
            raise RuntimeError("VTypeGen has an unreconciled slot after failure")
        if self._busy:
            raise RuntimeError("concurrent VTypeGen operations are not supported")
        self._busy = True

    async def _exchange(self, inputs: Inputs):
        edge = await self._driver.send(inputs)
        before, after = await self._monitor.recv()
        assert before.event.tick + 1 == edge.tick == after.event.tick, (
            "VTypeGen stale or missing phase snapshot")
        if self._last_tick is not None:
            assert edge.tick == self._last_tick + 2, (
                "VTypeGen skipped or repeated an input slot")
        self._last_tick = edge.tick
        return before, after

    async def _cycle_locked(self, inputs: Inputs) -> CheckedCycle:
        if not isinstance(inputs, Inputs):
            raise TypeError("VTypeGen requires semantic Inputs")
        try:
            expected_before = self._model.outputs(inputs)
            before, after = await self._exchange(inputs)
            self._model.tick(inputs)
            expected_after = self._model.outputs(inputs)
            # The lane window is combinational even while reset is asserted:
            # reset only clears the speculated/architectural registers, so a
            # driven vset lane still produces its own configuration.  The
            # model's reset expectation is therefore the same lane chain that
            # check_outputs compares; a fully quiet reset cycle observes the
            # INIT value (covered by the reset test).
            check_outputs(expected_before, before.value, phase="before")
            check_outputs(expected_after, after.value, phase="after")
            self.checked_cycles += 1
            return CheckedCycle(self.checked_cycles, before.event.tick, after.event.tick,
                                inputs, before.value, after.value, expected_before,
                                expected_after)
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
            await self._cycle_locked(Inputs())
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    @property
    def state(self) -> dict[str, object]:
        return self._model.snapshot()

    @property
    def cycle_count(self) -> int:
        return self.checked_cycles

    def audit(self) -> dict:
        return {
            "top": "VTypeGen",
            "inputs": sorted(INTERFACE["inputs"]),
            "outputs": sorted(INTERFACE["outputs"]),
            "absent": {},
            "vtype_outputs": 2 * 8 * 5,
            "isa_expectations": "RISC-V V 1.0 (vtype/vill/VLMAX) + interface contract",
        }

    async def cycle(self, inputs: Inputs = Inputs()) -> CheckedCycle:
        if not self._reset_done:
            raise RuntimeError("VTypeGen requires an explicit reset before input")
        self._enter_work()
        try:
            return await self._cycle_locked(inputs)
        finally:
            self._busy = False

    async def finish(self, max_cycles: int = 1) -> None:
        if self._finished:
            return
        if not isinstance(max_cycles, int) or max_cycles < 1:
            raise ValueError("finish requires a positive cycle budget")
        self._enter_work()
        try:
            if not self._reset_done:
                raise RuntimeError("VTypeGen requires an explicit reset before finish")
            for _ in range(max_cycles):
                await self._cycle_locked(Inputs())
            self._finished = True
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False
