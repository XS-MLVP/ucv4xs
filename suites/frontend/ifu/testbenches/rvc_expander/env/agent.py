"""Pure combinational decode with framework ownership, lossless sampling and drain."""
from contextlib import asynccontextmanager

from toffee import Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.frontend.ifu.testbenches.shared.env.driver.explicit_slots import ExplicitSlotDriver
from suites.frontend.ifu.testbenches.rvc_expander.model.rvc import Expansion

from suites.frontend.ifu.testbenches.rvc_expander.checker import check_decoding
from suites.frontend.ifu.testbenches.rvc_expander.env.ports import RvcPorts
from suites.frontend.ifu.testbenches.rvc_expander.transactions import CheckedDecode
from suites.frontend.ifu.testbenches.rvc_expander.transactions import IDLE


class RvcExpanderAgent:
    def __init__(self, harness):
        self.dut = harness.dut  # Coverage discovery only, never the feature-test API.
        self._clock = self.dut.GetXClock()  # Evaluates time, not a nonexistent RTL clock pin.
        self._ports = RvcPorts(self.dut)
        self._driver = ExplicitSlotDriver(self._clock, self._ports.bits,
            idle=self._ports.encode(IDLE), encoder=self._ports.encode, name='ifu.rvc_expander.inputs')
        self._monitor = None
        self._used = self._busy = self._finished = self._failed = False
        self._last_tick = None
        self.checked_slots = 0

    @asynccontextmanager
    async def running(self):
        if self._used:
            raise RuntimeError('RvcExpander agent cannot be restarted')
        self._used = True
        backend = XCommClockBackend(self._clock)
        try:
            async with Execution(backend) as execution:
                monitor = SamplingMonitor(RisingEdge(self._clock), capture=self._ports.capture)
                async with self._driver.holding(execution), monitor.start(execution):
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
            raise RuntimeError('RvcExpander requires its fixture-managed Execution')
        if self._finished:
            raise RuntimeError('RvcExpander input stream is finished')
        if self._failed:
            raise RuntimeError('RvcExpander has an unreconciled evaluation after failure/cancellation')
        if self._busy:
            raise RuntimeError('concurrent RvcExpander operations are not supported')
        self._busy = True

    async def _decode(self, request, expected=None):
        try:
            completed = await self._driver.send(request)
            observed = await self._monitor.recv()
            assert completed.tick == observed.event.tick, 'RvcExpander stale or missing snapshot'
            if self._last_tick is not None:
                assert completed.tick == self._last_tick + 2, 'RvcExpander skipped or repeated a slot'
            self._last_tick = completed.tick
            self.checked_slots += 1
            check_decoding(request, observed.value, expected)
            return CheckedDecode(self.checked_slots, observed.event.tick, observed.value)
        except BaseException:
            self._failed = True
            raise

    async def decode(self, request, *, expected=None):
        self._ports.encode(request)
        if expected is not None and not isinstance(expected, Expansion):
            raise TypeError('RvcExpander expected value must be an Expansion')
        self._enter_work()
        try:
            return await self._decode(request, expected)
        finally:
            self._busy = False

    async def finish(self):
        if self._finished:
            return
        self._enter_work()
        try:
            # There is no pipeline to drain. Check one defined idle evaluation
            # through the same monitor before closing, including full withdrawal.
            await self._decode(IDLE)
            self._finished = True
        finally:
            self._busy = False
