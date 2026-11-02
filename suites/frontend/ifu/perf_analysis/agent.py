"""Clocked reason transactions, immutable lossless observations and strict aging."""
from contextlib import asynccontextmanager

from toffee import DriveStable, Execution, SamplingMonitor, XCommClockBackend

from suites.frontend.ifu.drivers.explicit_slots import ExplicitSlotDriver

from suites.frontend.ifu.model.perf import Inputs, PerfModel, STAGES

from .checker import check_reasons
from .ports import Frame, PerfPorts


class PerfAnalysisAgent:
    def __init__(self, harness):
        self.dut = harness.dut  # Toffee native-coverage discovery boundary.
        self._ports = PerfPorts(self.dut)
        self._driver = ExplicitSlotDriver(self.dut.clock, self._ports.bits,
            idle=self._ports.encode(Frame()), encoder=self._ports.encode, name='ifu.perf_analysis.inputs')
        self._monitor = None
        self._used = self._busy = self._failed = self._finished = False
        self._last_tick = None
        self.model = PerfModel()
        self.checked_cycles = 0

    @asynccontextmanager
    async def running(self):
        if self._used:
            raise RuntimeError('PerfAnalysis agent cannot be restarted')
        self._used = True
        backend = XCommClockBackend(self.dut.GetXClock())
        try:
            async with Execution(backend) as execution:
                monitor = SamplingMonitor(DriveStable(self.dut.clock), capture=self._ports.capture)
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
            raise RuntimeError('PerfAnalysis requires its fixture-managed Execution')
        if self._busy:
            raise RuntimeError('concurrent PerfAnalysis cycle calls are not supported')
        if self._finished:
            raise RuntimeError('PerfAnalysis input stream is finished')
        if self._failed:
            raise RuntimeError('PerfAnalysis has an unreconciled input slot after failure/cancellation')
        self._busy = True

    async def _exchange(self, frame):
        edge = await self._driver.send(frame)
        observed = await self._monitor.recv()
        assert observed.event.tick + 1 == edge.tick, 'stale or missing PerfAnalysis snapshot'
        if self._last_tick is not None:
            assert edge.tick == self._last_tick + 2, 'PerfAnalysis skipped or repeated an input slot'
        self._last_tick = edge.tick
        return observed.value

    async def reset(self, cycles=3):
        if not isinstance(cycles, int) or cycles < 1:
            raise ValueError('reset requires a positive cycle budget')
        self._enter_work()
        try:
            for _ in range(cycles):
                await self._exchange(Frame(reset=True))
            self.model = PerfModel()
            observed = await self._exchange(Frame())
            check_reasons(observed, 0, note='PerfAnalysis reset')
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def _cycle(self, inputs):
        expected = self.model.output()
        observed = await self._exchange(Frame(inputs))
        # The real edge already occurred. Advance the independent state even if
        # a selftest subsequently rejects this observation; no imaginary rewind.
        self.model.tick(inputs)
        self.checked_cycles += 1
        check_reasons(observed, expected, note=f'PerfAnalysis cycle {self.checked_cycles}')
        return observed

    async def cycle(self, inputs=Inputs()):
        Frame(inputs)  # Reject malformed work before starting a sampled slot.
        self._enter_work()
        try:
            return await self._cycle(inputs)
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def finish(self):
        if self._finished:
            return
        # There is no ready/valid response transaction here: every slot in the
        # three-stage pipeline must be observed, including an empty aging slot.
        self._enter_work()
        try:
            for _ in range(STAGES + 1):
                await self._cycle(Inputs())
            assert not any(self.model.stages), 'PerfAnalysis still has in-flight reasons'
            self._finished = True
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False
