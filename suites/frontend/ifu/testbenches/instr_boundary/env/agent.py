"""Explicit combinational slots, lossless snapshots, and bounded whole-batch checking."""
from contextlib import asynccontextmanager

from toffee import Execution, RisingEdge, SamplingMonitor, ScoreboardMismatch, XCommClockBackend

from suites.frontend.ifu.testbenches.shared.env.driver.explicit_slots import ExplicitSlotDriver
from suites.frontend.ifu.testbenches.instr_boundary.model.boundary import BoundaryOutput

from suites.frontend.ifu.testbenches.instr_boundary.checker import check_boundary
from suites.frontend.ifu.testbenches.instr_boundary.env.ports import BoundaryPorts
from suites.frontend.ifu.testbenches.instr_boundary.transactions import BatchSummary
from suites.frontend.ifu.testbenches.instr_boundary.transactions import BoundaryBatchMismatch
from suites.frontend.ifu.testbenches.instr_boundary.transactions import CheckedBoundary
from suites.frontend.ifu.testbenches.instr_boundary.transactions import IDLE


class InstrBoundaryAgent:
    def __init__(self, harness):
        self.dut = harness.dut
        self._clock = self.dut.GetXClock()
        self._ports = BoundaryPorts(self.dut)
        self.interface = self._ports.interface
        self._driver = ExplicitSlotDriver(self._clock, self._ports.bits,
            idle=self._ports.encode(IDLE), encoder=self._ports.encode, name='ifu.instr_boundary.inputs')
        self._monitor = None
        self._used = self._busy = self._finished = self._failed = False
        self._last_tick = None
        self.checked_slots = 0
        self.sampled_slots = 0
        self.last_batch = None

    @asynccontextmanager
    async def running(self):
        if self._used:
            raise RuntimeError('InstrBoundary agent cannot be restarted')
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
            raise RuntimeError('InstrBoundary requires its fixture-managed Execution')
        if self._finished:
            raise RuntimeError('InstrBoundary input stream is finished')
        if self._failed:
            raise RuntimeError('InstrBoundary has an unreconciled evaluation after failure/cancellation')
        if self._busy:
            raise RuntimeError('concurrent InstrBoundary operations are not supported')
        self._busy = True

    async def _sample(self, request):
        completed = await self._driver.send(request)
        observed = await self._monitor.recv()
        assert completed.tick == observed.event.tick, 'InstrBoundary stale or missing snapshot'
        if self._last_tick is not None:
            assert completed.tick == self._last_tick + 2, 'InstrBoundary skipped or repeated a slot'
        self._last_tick = completed.tick
        self.sampled_slots += 1
        return CheckedBoundary(self.sampled_slots, observed.event.tick, observed.value)

    def _check(self, request, observed, expected=None):
        try:
            check_boundary(request, observed, expected)
        except ScoreboardMismatch:
            self.checked_slots += 1  # A real, discriminating failed comparison.
            raise
        else:
            self.checked_slots += 1

    async def analyze(self, request, *, expected=None):
        self._ports.encode(request)
        if expected is not None and not isinstance(expected, BoundaryOutput):
            raise TypeError('InstrBoundary expected value must be a BoundaryOutput')
        self._enter_work()
        try:
            observed = await self._sample(request)
            self._check(request, observed.result, expected)
            return observed
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def analyze_many(self, requests):
        if not isinstance(requests, (list, tuple)) or not requests:
            raise ValueError('InstrBoundary batch requires a nonempty finite sequence')
        requests = tuple(requests)
        for request in requests:
            self._ports.encode(request)
        self._enter_work()
        try:
            self.last_batch = None
            observations, failed, examples = [], [], []
            for index, request in enumerate(requests):
                observed = await self._sample(request)
                observations.append(observed)
                try:
                    self._check(request, observed.result)
                except ScoreboardMismatch as error:
                    # Only a completed, typed DUT comparison can accumulate.
                    # Clock, monitor, binding or transport failures abort immediately.
                    failed.append(index)
                    if len(examples) < 5:
                        examples.append(str(error))
            self.last_batch = BatchSummary(len(requests), tuple(failed))
            if failed:
                raise BoundaryBatchMismatch(self.last_batch, examples)
            return tuple(observations)
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def finish(self):
        if self._finished:
            return
        await self.analyze(IDLE)
        self._finished = True
