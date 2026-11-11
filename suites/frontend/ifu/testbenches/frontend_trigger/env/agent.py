"""One configuration edge, live gates, two immutable phase checks and strict tail."""
from contextlib import asynccontextmanager
from dataclasses import replace

from toffee import DriveStable, Execution, RisingEdge, SamplingMonitor, XCommClockBackend

from suites.frontend.ifu.testbenches.shared.env.driver.explicit_slots import ExplicitSlotDriver
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import ACTION_NONE
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import Inputs
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import LANES
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import TriggerModel

from suites.frontend.ifu.testbenches.frontend_trigger.checker import check_actions
from suites.frontend.ifu.testbenches.frontend_trigger.checker import require_csr_table
from suites.frontend.ifu.testbenches.frontend_trigger.env.ports import TriggerPorts
from suites.frontend.ifu.testbenches.frontend_trigger.transactions import CheckedCycle
from suites.frontend.ifu.testbenches.frontend_trigger.transactions import Frame


class FrontendTriggerAgent:
    def __init__(self, harness):
        self.dut = harness.dut  # Native coverage discovery only.
        self._ports = TriggerPorts(self.dut)
        self._driver = ExplicitSlotDriver(self.dut.clock, self._ports.bits,
            idle=self._ports.encode(Frame()), encoder=self._ports.encode, name='ifu.frontend_trigger.inputs')
        self._before = self._after = None
        self._model = TriggerModel()
        self._used = self._busy = self._failed = self._finished = self._reset_done = False
        self._last_tick = None
        self._last_inputs = Inputs()
        self.checked_cycles = 0

    @asynccontextmanager
    async def running(self):
        if self._used:
            raise RuntimeError('FrontendTrigger agent cannot be restarted')
        self._used = True
        backend = XCommClockBackend(self.dut.GetXClock())
        try:
            async with Execution(backend) as execution:
                before = SamplingMonitor(DriveStable(self.dut.clock), capture=self._ports.capture)
                after = SamplingMonitor(RisingEdge(self.dut.clock), capture=self._ports.capture)
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
            raise RuntimeError('FrontendTrigger requires its fixture-managed Execution')
        if self._finished:
            raise RuntimeError('FrontendTrigger input stream is finished')
        if self._failed:
            raise RuntimeError('FrontendTrigger has an unreconciled input slot after failure/cancellation')
        if self._busy:
            raise RuntimeError('concurrent FrontendTrigger operations are not supported')
        self._busy = True

    async def _exchange(self, frame):
        edge = await self._driver.send(frame)
        before, after = await self._before.recv(), await self._after.recv()
        assert before.event.tick + 1 == edge.tick == after.event.tick, 'FrontendTrigger stale or missing phase snapshot'
        if self._last_tick is not None:
            assert edge.tick == self._last_tick + 2, 'FrontendTrigger skipped or repeated an input slot'
        self._last_tick = edge.tick
        return before, after

    async def reset(self, cycles=3):
        if not isinstance(cycles, int) or cycles < 1:
            raise ValueError('reset requires a positive cycle budget')
        self._enter_work()
        try:
            for _ in range(cycles):
                _, after = await self._exchange(Frame(reset=1))
                check_actions(after.value, (ACTION_NONE,) * LANES, phase='reset')
            self._model = TriggerModel()
            self._reset_done = True
            await self._cycle(Inputs())
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def _cycle(self, inputs):
        expected_before = self._model.lane_actions(inputs)
        before, after = await self._exchange(Frame(inputs))
        # The physical edge happened, even if comparison subsequently fails.
        self._model.tick(inputs)
        self._last_inputs = inputs
        expected_after = self._model.lane_actions(inputs)
        self.checked_cycles += 1
        observed = CheckedCycle(self.checked_cycles, before.event.tick, after.event.tick,
                                before.value, after.value)
        check_actions(observed.before, expected_before, phase='before')
        check_actions(observed.after, expected_after, phase='after')
        return observed

    async def _submit(self, inputs, *, producer):
        if not isinstance(inputs, Inputs):
            raise TypeError('FrontendTrigger requires semantic Inputs')
        if producer:
            require_csr_table(self._model.triggers)
            candidate = list(self._model.triggers)
            if inputs.update.valid:
                candidate[inputs.update.index] = inputs.update.trigger
            require_csr_table(candidate)
        self._enter_work()
        try:
            if not self._reset_done:
                raise RuntimeError('FrontendTrigger requires an explicit reset before input')
            return await self._cycle(inputs)
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def cycle(self, inputs=Inputs()):
        """CSR-reachable configuration encodings and pairwise chain history."""
        return await self._submit(inputs, producer=True)

    async def characterize_cycle(self, inputs):
        """Explicit leaf-port stress: no CSR provenance credit, same strict checks."""
        return await self._submit(inputs, producer=False)

    async def finish(self):
        if self._finished:
            return
        self._enter_work()
        try:
            if not self._reset_done:
                raise RuntimeError('FrontendTrigger requires an explicit reset before finish')
            idle = replace(Inputs(), pcs=self._last_inputs.pcs)
            await self._cycle(idle)  # Observe final config, then register disable.
            await self._cycle(idle)  # Observe quiet after disable, not a dropped tail.
            self._finished = True
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False
