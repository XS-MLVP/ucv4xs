"""Persistent BPU controls plus a monitor-terminated prediction window."""
from dataclasses import dataclass
from collections.abc import Callable
from asyncio import Future

from toffee import AnyOf, ClockCycles, TaskComplete, SimTimeout, XEvent, XEventKind, XPhase
from toffee import PythonPredicateTrigger, RisingEdge
from toffee.data import drive_data

from bpuverify.common.driver.signal import ClockedWriteDriver


@dataclass(frozen=True, slots=True)
class PredictionWindow:
    values: dict
    accepted: Future
    name: str
    timeout_cycles: int = 64
    failure: Callable[[], BaseException | None] | None = None
    prediction_ready: bool = True
    prepared: Future | None = None

    def __post_init__(self):
        if not isinstance(self.accepted, Future) or self.accepted.done() or not self.name:
            raise ValueError('prediction window needs a fresh actual-acceptance future')
        if self.failure is not None and not callable(self.failure):
            raise ValueError('prediction window failure provider must be callable')
        if type(self.timeout_cycles) is not int or self.timeout_cycles <= 0:
            raise ValueError('prediction window timeout must be a positive failure budget')
        if type(self.prediction_ready) is not bool:
            raise ValueError('prediction window level must be a boolean')
        if self.prepared is not None and (not isinstance(self.prepared, Future) or self.prepared.done()):
            raise ValueError('window preparation needs a fresh future')


class BpuControlDriver(ClockedWriteDriver):
    """Keep existing persistent writes unchanged; own window opening/closing."""
    async def _drive_one(self, transaction):
        if not isinstance(transaction, PredictionWindow):
            return await super()._drive_one(transaction)
        opened = dict(transaction.values, prediction_ready=int(transaction.prediction_ready))
        closed = dict(transaction.values, prediction_ready=int(not transaction.prediction_ready))
        async def confirmed(future, phase):
            guards = [TaskComplete(future),
                      SimTimeout(transaction.timeout_cycles, clock=self.binding.clock)]
            if transaction.failure is not None:
                guards.append(PythonPredicateTrigger(transaction.name+'.failure',
                    lambda: transaction.failure() is not None,
                    sample=RisingEdge(self.binding.clock), mode='each_sample'))
            wake = await AnyOf(*guards)
            error = None if transaction.failure is None else transaction.failure()
            if error is not None:
                raise error
            # The future is completed by the monitor capture after its actual
            # comparison. Backend predicates run BEFORE @on capture, so polling
            # monitor state would close one rising boundary too late.
            if future.done():
                accepted = future.result()
                if (not isinstance(accepted, XEvent) or accepted.tick < 0
                        or accepted.phase is not phase):
                    label = 'real rising-stable acceptance' if phase is XPhase.RISING_STABLE else 'real drive-stable preparation'
                    raise TypeError('prediction window requires the '+label+' XEvent')
                return accepted
            if wake.kind is XEventKind.TIMEOUT:
                raise TimeoutError(transaction.name+': original source was not accepted before the deadline')
            raise AssertionError('prediction window woke without an actual acceptance or failure')
        try:
            drive_data(self.binding.bits, opened, self.binding.name)
            prepared = None
            if transaction.prepared is not None:
                # Rise-write commits AFTER the rising edge. Schedule closure
                # on the pre-edge candidate, then require the actual compared
                # SDK receipt. A candidate alone never completes this window.
                prepared = await confirmed(transaction.prepared, XPhase.DRIVE_STABLE)
                if transaction.accepted.done():
                    raise AssertionError('window preparation arrived after actual acceptance')
                drive_data(self.binding.bits, closed, self.binding.name)
            accepted = await confirmed(transaction.accepted, XPhase.RISING_STABLE)
            if prepared is not None and accepted.tick != prepared.tick + 1:
                raise AssertionError('prepared window lacks its exact following rising acceptance')
            return accepted
        finally:
            drive_data(self.binding.bits, closed, self.binding.name)
            # Commit the restored level. The duration of the open window was
            # determined by actual acceptance, not by this protocol tail.
            await ClockCycles(self.binding.clock, 1)
