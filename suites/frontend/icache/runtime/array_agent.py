"""Shared SRAM execution mechanics; protocol/storage semantics stay in each DUT.

SDK drivers own inputs and SDK monitors deliver lossless complete phase frames.
This class only serializes declared cycles, consumes the paired frames and
enforces checked lifecycle. It never imports a DUT model, decodes a payload,
chooses a response time from expected values or implements SDK association.
"""
import asyncio
from contextlib import asynccontextmanager
from toffee import ClockCycles, DriveStable, RisingEdge
from suites.frontend.icache.drivers.level import LevelDriver
from suites.frontend.icache.drivers.signal import ResetDriver
from suites.frontend.icache.transactions.sram import SramControls, encode_controls

_DEFAULT_CYCLE = object()


class ArrayAgent:
    def __init__(self, dut, ports, checker, *, cycle_type, encoder, monitor_type,
                 bindings, control_groups, label):
        self.dut, self.ports, self.checker = dut, ports, checker
        self._cycle_type, self._encoder, self.label = cycle_type, encoder, label
        self._control_groups = control_groups
        self._drivers = {name: LevelDriver(binding) for name, binding in bindings.items()}
        for name, driver in self._drivers.items():
            setattr(self, name + '_driver', driver)
        self.control_driver = LevelDriver(ports.sram_control)
        self.reset_driver = ResetDriver(dut)
        self._idle_controls = SramControls.idle(control_groups)
        self.before_monitor = monitor_type(DriveStable(dut.clock), dut, ports)
        self.after_monitor = monitor_type(RisingEdge(dut.clock), dut, ports)
        self._execution = None
        self._used = self._finished = False
        self._lock = asyncio.Lock()
        self._consumer = None
        self._progress, self._failed = asyncio.Event(), asyncio.Event()
        self._failure = None
        self._last_tick = 0
        self._latest = None

    def _raise_failure(self):
        error = self._failure or self.checker.board.status.first_failure
        if error is not None:
            raise error

    def _active(self):
        if self._execution is None:
            raise RuntimeError(f'{self.label} requires an active agent')
        self._raise_failure()
        if self._finished:
            raise RuntimeError(f'{self.label} is already finished')
        if not self.before_monitor.active or not self.after_monitor.active:
            raise RuntimeError(f'{self.label} lost a required sampling monitor')
        if self._consumer is None or self._consumer.done():
            raise RuntimeError(f'{self.label} lost its unique sampling consumer')

    async def start(self, execution):
        if self._used:
            raise RuntimeError(f'{self.label} agent cannot be restarted')
        self._used = True
        self._execution = execution
        try:
            await self.reset_driver.__aenter__()
            self.idle_inputs()
            self.before_monitor.start(execution)
            self.after_monitor.start(execution)
            self._consumer = asyncio.create_task(self._consume())
            await self.reset()
        except BaseException:
            await self.aclose()
            raise
        return self

    async def _consume(self):
        try:
            while True:
                before, after = await self.before_monitor.recv(), await self.after_monitor.recv()
                self._latest = self.checker.observe(before, after)
                self._last_tick = after.event.tick
                self._progress.set()
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            self._failure = error
            self._failed.set()
            self._progress.set()
        finally:
            # A cancelled sole consumer must wake an already-waiting cycle or
            # reset.  Its disappearance is not an empty successful frame.
            self._failed.set()
            self._progress.set()

    async def _caught_up(self, tick):
        while self._last_tick < tick:
            self._active()
            self._progress.clear()
            await self._progress.wait()
        self._active()

    async def _edge(self):
        self._active()
        event = await ClockCycles(self.dut.clock, 1)
        await self._caught_up(event.tick)
        return event

    def idle_inputs(self):
        values = self._encoder(self._cycle_type())
        for name, driver in self._drivers.items():
            driver.set(values[name])
        self.control_driver.set(encode_controls(self._idle_controls))

    def _set_controls(self, controls):
        if type(controls) is not SramControls:
            raise ValueError(f'{self.label} controls require SramControls')
        controls.require_groups(self._control_groups)
        self.control_driver.set(encode_controls(controls))

    @asynccontextmanager
    async def _operation(self):
        self._active()
        async with self._lock:
            self._active()
            yield

    async def _cycle(self, cycle):
        tick = (self._execution.backend.tick // 2 + 1) * 2
        controls = getattr(cycle, 'controls', None)
        if controls is not None:
            controls.require_groups(self._control_groups)
            self._set_controls(controls)
        self.checker.plan(tick, cycle)
        values = self._encoder(cycle)
        for name, driver in self._drivers.items():
            driver.set(values[name])
        await self._edge()
        for result in self._latest.responses:
            self.checker.deliver(result, result.values)
        return self._latest

    async def cycle(self, cycle=_DEFAULT_CYCLE):
        if cycle is _DEFAULT_CYCLE:
            cycle = self._cycle_type()
        if type(cycle) is not self._cycle_type:
            raise ValueError(f'{self.label} cycle requires {self._cycle_type.__name__}')
        async with self._operation():
            return await self._cycle(cycle)

    async def settle(self, cycles=1):
        if type(cycles) is not int or cycles < 0:
            raise ValueError(f'{self.label} settle requires nonnegative integer cycles')
        async with self._operation():
            for _ in range(cycles):
                await self._cycle(self._cycle_type())
            return self._latest

    async def reset(self, cycles=4):
        if type(cycles) is not int or cycles <= 0:
            raise ValueError(f'{self.label} reset requires a positive integer cycle count')
        async with self._operation():
            start = (self._execution.backend.tick // 2 + 1) * 2
            self.checker.plan_reset(start, cycles)
            self.idle_inputs()
            driving = asyncio.create_task(self.reset_driver.send(cycles))
            failed = asyncio.create_task(self._failed.wait())
            try:
                await asyncio.wait((driving, failed), return_when=asyncio.FIRST_COMPLETED)
                self._raise_failure()
                await driving
                await self._caught_up(self._execution.backend.tick)
            finally:
                for task in (driving, failed):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(driving, failed, return_exceptions=True)

    def read_ready(self):
        self._active()
        return self._latest.read_ready

    def write_ready(self):
        self._active()
        return self._latest.write_ready

    def settle_cycles(self):
        return self.geometry.sets + 32

    async def wait_for(self, predicate, *, what, cycles=None):
        cycles = self.settle_cycles() if cycles is None else cycles
        if type(cycles) is not int or cycles < 0:
            raise ValueError(f'{self.label} wait requires nonnegative integer cycles')
        for _ in range(cycles):
            self._active()
            if predicate():
                return
            await self._edge()
        if not predicate():
            raise TimeoutError(f'{what} did not happen within {cycles} edges')

    async def wait_ready(self):
        async with self._operation():
            await self.wait_for(lambda: self.read_ready() and self.write_ready(), what='SRAM initialization')
            return self._latest

    def receipt(self):
        return dict(finished=self._finished, epoch=self.checker.epoch, tick=self._last_tick,
            checked=self.checker.board.status.checked, inputs=self.checker.rows)

    async def finish(self):
        self._raise_failure()
        if self._finished:
            return self.receipt()
        self._active()
        if self._lock.locked():
            raise RuntimeError(f'{self.label} has active transaction work')
        # Check both unlaunched declarations and actual held offers BEFORE a
        # drain clock: a cancelled read/reset cannot be executed as cleanup.
        self.checker.require_idle_inputs()
        self.checker.require_idle_controls()
        for _ in range(self.settle_cycles()):
            self._raise_failure()
            if self.checker.quiescent() and self._latest.write_ready:
                break
            await self._edge()
        self.checker.finish()
        self.checker.check(1, self._latest.write_ready)
        self._finished = True
        return self.receipt()

    async def aclose(self):
        """Cleanup only. Passing/missing-report fixtures must first finish."""
        errors = []
        if self._consumer is not None:
            self._consumer.cancel()
            await asyncio.gather(self._consumer, return_exceptions=True)
            self._consumer = None
        for monitor in (self.before_monitor, self.after_monitor):
            try:
                await monitor.aclose()
            except BaseException as error:
                errors.append(error)
        for driver in (*self._drivers.values(), self.control_driver, self.reset_driver):
            try:
                driver.close()
            except BaseException as error:
                errors.append(error)
        self._execution = None
        if errors:
            raise BaseExceptionGroup(f'{self.label} independent cleanup errors', errors)
