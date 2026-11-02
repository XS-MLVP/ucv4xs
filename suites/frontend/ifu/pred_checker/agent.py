"""Two-phase transaction agent: combinational truncation, then registered redirect."""
from contextlib import asynccontextmanager
import random

from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.frontend.ifu.model.pred_checker import PC_BITS, Redirect, Request, predict

from .checker import check_prediction
from .driver import PredCheckerDriver
from .ports import PredCheckerPorts
from .types import CheckedCycle, Frame


class PredCheckerAgent:
    def __init__(self, harness):
        self.dut = harness.dut  # Native coverage discovery boundary, not a test API.
        self._ports = PredCheckerPorts(self.dut)
        self.interface = self._ports.interface
        self._driver = PredCheckerDriver(self.dut.clock, self._ports)
        self._before = self._after = None
        self._used = self._busy = self._finished = False
        self._previous = Redirect()
        self._failed = False
        self._last_tick = None
        self._padding = random.Random(0x35)
        self.checked_cycles = 0

    @asynccontextmanager
    async def running(self):
        if self._used:
            raise RuntimeError('PredChecker agent cannot be restarted')
        self._used = True
        backend = XCommClockBackend(self.dut.GetXClock())
        try:
            async with Execution(backend) as execution:
                before = SamplingMonitor(DriveStable(self.dut.clock), capture=self._ports.capture_before)
                after = SamplingMonitor(RisingEdge(self.dut.clock), capture=self._ports.capture_redirect)
                async with self._driver.holding(execution), before.start(execution), after.start(execution):
                    self._before, self._after = before, after
                    try:
                        yield self
                        await self.finish()
                    finally:
                        self._before = self._after = None
        finally:
            backend.close()

    def _enter_work(self):
        if self._before is None or self._after is None:
            raise RuntimeError('PredChecker requires its fixture-managed Execution')
        if self._finished:
            raise RuntimeError('PredChecker input stream is finished')
        if self._failed:
            raise RuntimeError('PredChecker has an unreconciled input slot after failure/cancellation')
        if self._busy:
            raise RuntimeError('concurrent PredChecker operations are not supported')
        self._busy = True

    async def _exchange(self, frame):
        try:
            edge = await self._driver.send(frame)
            before = await self._before.recv()
            after = await self._after.recv()
            assert before.event.tick + 1 == edge.tick == after.event.tick, (
                'PredChecker stale or missing phase snapshot')
            if self._last_tick is not None:
                assert edge.tick == self._last_tick + 2, 'PredChecker skipped or repeated an input slot'
            self._last_tick = edge.tick
            return before, after
        except BaseException:
            self._failed = True
            raise

    async def reset(self, cycles=3):
        if not isinstance(cycles, int) or cycles < 1:
            raise ValueError('reset requires a positive cycle budget')
        self._enter_work()
        try:
            for _ in range(cycles):
                before, after = await self._exchange(Frame(reset=True))
                assert after.value.valid == 0, 'PredChecker reset did not cancel the redirect'
            self._previous = Redirect()
            await self._cycle(Request(valid=0))
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def _cycle(self, request):
        frame = Frame(request, padding_pc=self._padding.getrandbits(PC_BITS) & ~1)
        expected, previous = predict(request), self._previous
        before, after = await self._exchange(frame)
        self.checked_cycles += 1
        # The physical edge happened even if an injected observation fails below.
        self._previous = expected.redirect
        observed = CheckedCycle(self.checked_cycles, before.value.fixed_instr_valid,
            before.value.redirect, after.value, before.event.tick, after.event.tick)
        try:
            check_prediction(observed, expected, previous)
        except AssertionError:
            self._failed = True
            raise
        return observed

    async def cycle(self, request=Request(valid=0)):
        self._enter_work()
        try:
            return await self._cycle(request)
        finally:
            self._busy = False

    async def finish(self):
        if self._finished:
            return
        self._enter_work()
        try:
            # First clear the registered response, then observe a further empty
            # slot. Never hide a stale/duplicate redirect by closing a monitor.
            await self._cycle(Request(valid=0))
            await self._cycle(Request(valid=0))
            self._finished = True
        finally:
            self._busy = False
