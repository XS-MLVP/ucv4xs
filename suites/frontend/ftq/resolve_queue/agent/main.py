"""ResolveQueue agent: owns drivers, monitors and the checker glue."""

from __future__ import annotations

from typing import Iterable, Sequence
from suites.frontend.ftq.monitors.cycle import EdgeMonitor
from suites.frontend.ftq.harness import Dut
from suites.frontend.ftq.resolve_queue.bundle.ports import ResolveQueuePorts
from suites.frontend.ftq.resolve_queue.checker.model import ResolveChecker
from suites.frontend.ftq.resolve_queue.monitor.decode import decode_training
from suites.frontend.ftq.resolve_queue.transaction.types import ResolveReport
from suites.frontend.ftq.resolve_queue.transaction.types import Training
from suites.frontend.ftq.resolve_queue.transaction.cycle import ResolveInput
from suites.frontend.ftq.resolve_queue.driver.slots import ResolveInputDriver
from suites.frontend.ftq.resolve_queue.checker.transactions import ResolveTransactions


class ResolveQueueAgent:
    def __init__(self, dut: Dut) -> None:
        self.dut = dut
        self.ports = ResolveQueuePorts.bind(dut)
        self.input_driver = ResolveInputDriver(dut, self.ports)
        self.training_monitor = EdgeMonitor(
            "resolve_queue.training", lambda d: decode_training(d, self.ports.train))
        self.checker = ResolveChecker()
        self.transactions = ResolveTransactions()
        self._started = False
        self._used = self._busy = self._failed = self._finished = False
        self._ready = False
        self._slot = 0
        self._inflight = None

    async def start(self) -> "ResolveQueueAgent":
        if self._used:
            raise RuntimeError('ResolveQueue agent cannot be restarted')
        self._used = True
        self.dut.add_monitor(self.training_monitor)
        await self.input_driver.__aenter__()
        self._started = True
        try:
            await self.reset()
        except BaseException:
            await self.aclose()
            raise
        return self

    async def aclose(self) -> None:
        self.input_driver.close()
        self._started = False

    def _enter_work(self):
        if not self._started:
            raise RuntimeError('ResolveQueue agent is not running')
        if self._busy:
            raise RuntimeError('concurrent ResolveQueue input work is not supported')
        if self._failed or self._inflight is not None:
            raise RuntimeError('ResolveQueue has unreconciled input work after failure/cancellation')
        if self._finished:
            raise RuntimeError('ResolveQueue input stream is finished')
        self.transactions.require_clean()
        if self.checker.scoreboard.status.failed:
            raise RuntimeError('resolve_queue has a prior public reference failure')
        self.dut.check_sampling()
        self._busy = True

    async def _cycle(self, frame):
        self._slot += 1
        self._inflight = frame
        event = await self.input_driver.send(frame)
        cycle = self.dut.cycle_history[-1]
        assert cycle.after.event.tick == event.tick, 'resolve_queue input/observation tick mismatch'
        actual_inputs = dict(cycle.before.value.inputs)
        self.transactions.scoreboard.check(expected=self.ports.encode(frame), actual=actual_inputs)
        before = dict(cycle.before.value.observations)['resolve_queue.training']
        after = dict(cycle.after.value.observations)['resolve_queue.training']
        self.transactions.advance_slot(frame, self._slot, before, after, event.tick)
        self._inflight = None

    async def _run(self, frames):
        frames = tuple(frames)
        for frame in frames:
            self.ports.encode(frame)  # Validate the whole operation before work.
        self._enter_work()
        try:
            for frame in frames:
                await self._cycle(frame)
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    def _frame(self, **values):
        return ResolveInput(ready=self._ready, **values)

    async def reset(self, *, asserted: int = 2, released: int = 2) -> None:
        if any(type(value) is not int or value < 1 for value in (asserted, released)):
            raise ValueError('ResolveQueue reset needs positive integer budgets')
        self._ready = False
        await self._run((ResolveInput(reset=True),) * asserted + (ResolveInput(),) * released)
        self.checker = ResolveChecker()

    async def ready(self, enabled: bool = True) -> None:
        if type(enabled) is not bool:
            raise ValueError('ResolveQueue readiness requires a semantic bool')
        self._enter_work()
        try:
            self._ready = enabled
        finally:
            self._busy = False

    async def resolve(self, reports: Iterable[ResolveReport], *, source: str = "backend") -> None:
        """Drive one cycle of reports (backend lanes or IFU), then release."""

        reports = tuple(reports)
        if not reports:
            raise ValueError("resolve() needs at least one report")
        if source == "backend":
            if len(reports) > 3:
                raise ValueError("backend accepts at most three lane reports")
            frame = self._frame(backend=reports + (None,) * (3 - len(reports)))
        elif source == "ifu":
            if len(reports) != 1:
                raise ValueError("IFU accepts exactly one resolve report")
            frame = self._frame(ifu=reports[0])
        else:
            raise ValueError(f"unknown source {source!r}")
        await self._run((frame, self._frame()))

    async def resolve_mixed(self, backend: Sequence[ResolveReport | None] = (),
                            ifu: ResolveReport | None = None) -> None:
        """Drive backend lanes and the IFU source in the same cycle.

        ``None`` entries leave that backend lane idle, so a caller can place a
        report in any specific lane instead of always starting at lane 0.
        """

        if len(backend) > 3:
            raise ValueError("backend accepts at most three lane reports")
        frame = self._frame(backend=tuple(backend) + (None,) * (3 - len(backend)), ifu=ifu)
        await self._run((frame, self._frame()))

    async def backend_lanes(self, lanes: Sequence[ResolveReport | None]) -> None:
        """Drive backend lanes with explicit valid/invalid payloads."""

        if len(lanes) != 3:
            raise ValueError("backend lane vector has exactly three entries")
        await self._run((self._frame(backend=tuple(lanes)), self._frame()))

    async def redirect(self, index: int, flag: int = 0) -> None:
        await self._run((self._frame(redirect=(flag, index)), self._frame()))

    async def bpu_enqueue(self, index: int) -> None:
        await self._run((self._frame(enqueue=index), self._frame()))

    async def step(self, cycles: int = 1) -> None:
        if type(cycles) is not int or cycles < 1:
            raise ValueError('ResolveQueue step needs a positive integer cycle budget')
        await self._run((self._frame(),) * cycles)

    async def cycle(self, frame: ResolveInput):
        """One explicit simultaneous semantic slot, without a release edge."""
        await self._run((frame,))
        self._ready = frame.ready

    def training(self) -> Training | None:
        if self._failed or self._inflight is not None:
            raise RuntimeError('ResolveQueue has unreconciled input work after failure/cancellation')
        self.transactions.require_clean()
        value = self.training_monitor.sample(self.dut)
        self.transactions.scoreboard.check(expected=self.transactions.visible(self._frame()), actual=value)
        return value

    def take_training(self) -> Training | None:
        value = self.training_monitor.latest
        self.training_monitor.latest = None
        return value

    def receipt(self):
        if self._failed or self._inflight is not None:
            raise RuntimeError('ResolveQueue has unreconciled input work after failure/cancellation')
        self.dut.check_sampling()
        if self.checker.scoreboard.status.failed:
            raise RuntimeError('resolve_queue has a prior public reference failure')
        return self.transactions.receipt()

    async def drain_all(self, *, cycles=20):
        """Explicit consumer schedule; never invoked implicitly by finish/close."""
        if type(cycles) is not int or cycles < 1:
            raise ValueError('ResolveQueue drain needs a positive integer cycle budget')
        await self.ready(True)
        for _ in range(cycles):
            await self.step(1)
            if not self.transactions.entries:
                break
        else:
            self._failed = True
            raise AssertionError('resolve_queue explicit drain budget exhausted')
        await self.ready(False)
        await self.step(2)

    async def finish(self, *, cycles=20):
        if self._finished:
            return self.receipt()
        if type(cycles) is not int or cycles < 2:
            raise ValueError('ResolveQueue finish needs at least two idle cycles')
        self._enter_work()
        try:
            if self.transactions.audit() and not self._ready:
                raise AssertionError('resolve_queue accepted reports remain while consumer is not ready; explicitly drain')
            quiet = 0
            for _ in range(cycles):
                await self._cycle(self._frame())
                self.transactions.audit()
                quiet = quiet + 1 if not self.transactions.entries else 0
                if quiet >= 2:
                    break
            else:
                raise AssertionError('resolve_queue finish budget exhausted')
            assert not self.transactions.audit(), 'resolve_queue accepted reports remain unfinished'
            self._finished = True
            return self.receipt()
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def wait_training(self, cycles: int = 8) -> Training:
        if type(cycles) is not int or cycles < 1:
            raise ValueError('ResolveQueue wait needs a positive integer cycle budget')
        for _ in range(cycles):
            value = self.training()
            if value is not None:
                return value
            await self.step(1)
        self._failed = True
        raise AssertionError('resolve_queue did not present a promised training entry')

    async def drain(self, *, cycles: int = 8) -> Training:
        value = await self.wait_training(cycles)
        await self.ready(True)
        await self.step(1)
        await self.ready(False)
        await self.step(1)
        return value

    # Ownership/identity observables; payload expectations come from the checker.
    def enq_ptr(self) -> int:
        return self.dut.internal("ResolveQueueDut_top.ResolveQueue.enqPtr_value")

    def deq_ptr(self) -> int:
        return self.dut.internal("ResolveQueueDut_top.ResolveQueue.deqPtr_value")
