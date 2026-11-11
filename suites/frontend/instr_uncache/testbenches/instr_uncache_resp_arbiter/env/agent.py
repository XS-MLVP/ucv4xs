"""Combinational evaluation agent for Arbiter1_InstrUncacheResp."""

from __future__ import annotations

from contextlib import asynccontextmanager

from toffee import Execution, XCommClockBackend

from suites.frontend.instr_uncache.testbenches.shared.env.drivers.slot import ExplicitSlotDriver
from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.model import Inputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.model import Outputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.model import arbiter_outputs

from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.checker import check_outputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.env.ports import INTERFACE
from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.env.ports import RespArbiterPorts


class RespArbiterAgent:
    def __init__(self, harness):
        self.dut = harness.dut  # Native coverage discovery, never a test API.
        self.interface = INTERFACE
        self._ports = RespArbiterPorts(self.dut)
        self._clock = self.dut.GetXClock()
        self._driver = ExplicitSlotDriver(
            self._clock, self._ports.bits,
            idle=self._ports.encode(Inputs()),
            encoder=self._ports.encode,
            name="instr_uncache.resp_arbiter.inputs",
        )
        self._monitor = None
        self._used = self._busy = self._finished = self._failed = False
        self._last_tick = None
        self.checked_vectors = 0

    @asynccontextmanager
    async def running(self):
        if self._used:
            raise RuntimeError("resp arbiter agent cannot be restarted")
        self._used = True
        from suites.frontend.instr_uncache.testbenches.shared.env.monitors.cycle import SinglePhaseMonitor
        monitor = SinglePhaseMonitor(self._clock, self._ports.capture)
        backend = XCommClockBackend(self._clock)
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
            raise RuntimeError("resp arbiter requires its fixture-managed Execution")
        if self._finished:
            raise RuntimeError("resp arbiter input stream is finished")
        if self._failed:
            raise RuntimeError("resp arbiter has an unreconciled vector after failure")
        if self._busy:
            raise RuntimeError("concurrent resp arbiter operations are not supported")
        self._busy = True

    async def _evaluate_locked(self, inputs: Inputs) -> Outputs:
        if not isinstance(inputs, Inputs):
            raise TypeError("resp arbiter requires semantic Inputs")
        try:
            expected = arbiter_outputs(inputs)
            edge = await self._driver.send(inputs)
            observed = await self._monitor.recv()
            assert edge.tick == observed.event.tick, "resp arbiter stale snapshot"
            if self._last_tick is not None:
                assert edge.tick == self._last_tick + 2, "resp arbiter skipped a slot"
            self._last_tick = edge.tick
            check_outputs(expected, observed.value)
            self.checked_vectors += 1
            return observed.value
        except BaseException:
            self._failed = True
            raise

    async def evaluate(self, inputs: Inputs) -> Outputs:
        if not isinstance(inputs, Inputs):
            raise TypeError("resp arbiter requires semantic Inputs")
        self._enter_work()
        try:
            return await self._evaluate_locked(inputs)
        finally:
            self._busy = False

    async def reset(self) -> None:
        self._enter_work()
        try:
            await self._evaluate_locked(Inputs())
        finally:
            self._busy = False

    def audit(self) -> dict:
        return {"top": "Arbiter1_InstrUncacheResp",
                "inputs": sorted(INTERFACE["inputs"]),
                "outputs": sorted(INTERFACE["outputs"]),
                "absent": dict(INTERFACE["absent"])}

    async def finish(self) -> None:
        if self._finished:
            return
        self._enter_work()
        try:
            observed = await self._evaluate_locked(Inputs())
            assert observed == Outputs(0, 0, 0, 0, 0)
            self._finished = True
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False
