"""suites.frontend.bpu.uras.agent.main components."""

from __future__ import annotations
from dataclasses import asdict
from typing import Any
from typing import Iterable
from toffee import Execution
from suites.frontend.bpu.drivers.signal import ClockedWriteDriver
from suites.frontend.bpu.transactions.cycle import CycleTransaction
from suites.frontend.bpu.drivers.signal import ResetDriver
from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.uras.transaction.types import UrasCycle
from suites.frontend.bpu.uras.bundle.ports import UrasPorts
from suites.frontend.bpu.uras.transaction.types import UrasResult
from suites.frontend.bpu.uras.checker.semantic import UrasSemanticChecker
from suites.frontend.bpu.uras.monitor.semantic import UrasSemanticMonitor
from suites.frontend.bpu.uras.coverage.semantic import UrasSemanticCoverage
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.uras.model.semantic import RasEvents


def encode_events(events: RasEvents) -> UrasCycle:
    """Encode public operation events; simulator phases stay in the driver."""
    if not isinstance(events, RasEvents) or events.reset:
        raise ValueError('apply accepts RasEvents; use reset() for a reset epoch')
    values = dict(full_ret_addr=events.main_top, s2_fire=int(events.advance),
                  s3_fire=int(events.retire), has_redirect=int(events.redirect))
    for prefix, operation, qualifier in (
        ('spec', events.accept, 's1_fire'),
        ('s2', events.correct_pending, 's2_valid'),
        ('s3', events.correct_retiring, 's3_valid'),
    ):
        if operation is not None:
            values.update({qualifier: 1, prefix + '_action': int(operation.action),
                           prefix + '_start_pc': operation.pc, prefix + '_position': operation.position})
    return UrasCycle(**values)


class UrasAgent:
    def __init__(self, dut: Any) -> None:
        self.dut = dut
        self.ports = UrasPorts.bind(dut)
        self.reset_driver = ResetDriver(dut)
        self.write_driver = ClockedWriteDriver(self.ports.stimulus)
        self.result_monitor = CycleMonitor(
            self.ports.result,
            decoder=lambda sample: UrasResult(
                sample.usable.as_int(), sample.target.as_int()
            ),
        )
        self.reference_coverage = UrasSemanticCoverage()
        self.reference = UrasSemanticChecker(coverage=self.reference_coverage)
        self.reference_monitor = UrasSemanticMonitor(dut, self.ports)
        self._started = False

    async def start(self, execution: Execution) -> "UrasAgent":
        if self._started:
            raise RuntimeError("MicroRAS agent is already started")
        await self.reset_driver.__aenter__()
        await self.write_driver.__aenter__()
        self.reference_monitor.start(execution, self.reference)
        self._started = True
        return self

    async def aclose(self) -> None:
        await self.reference_monitor.aclose()
        self.write_driver.close()
        self.reset_driver.close()
        self._started = False
        self.reference_coverage.write(output_directory(REPO_ROOT, 'uras'))
        self.reference.raise_unobserved_failure()

    async def reset(self, cycles: int = 2) -> None:
        self._require_started()
        await self.reset_driver.send(cycles)
        status = self.ports.status.bits.sample()
        if not status.reset_done.as_int() or not status.train_ready.as_int():
            raise AssertionError("MicroRAS did not become ready after reset")
        self.reference.raise_failure()

    def _cycle_values(self, transaction: UrasCycle) -> dict[str, Any]:
        values = asdict(transaction)
        # The enable field states the intended parent policy; DefaultConfig
        # MicroRas has no such pin, so it must not be driven into the DUT.
        values.pop('enable', None)
        return values

    async def cycle(self, transaction: UrasCycle) -> UrasResult:
        self._require_started()
        event = await self.write_driver.send(
            CycleTransaction(self._cycle_values(transaction), cycles=1)
        )
        actual = self.result_monitor.sample_at(event).value
        self.reference.raise_failure()
        return actual

    async def pulse(self, transaction: UrasCycle) -> UrasResult:
        """Apply a stage-control transaction once, then restore idle inputs."""

        self._require_started()
        await self.write_driver.send(CycleTransaction(self._cycle_values(transaction), cycles=0))
        event = await self.write_driver.send(
            CycleTransaction(self._cycle_values(UrasCycle()), cycles=0))
        actual = self.result_monitor.sample_at(event).value
        self.reference.raise_failure()
        return actual

    async def apply(self, events: RasEvents) -> UrasResult:
        """Apply one semantic operation boundary, then withdraw its proposal."""
        return await self.pulse(encode_events(events))

    async def stream(self, transactions: Iterable[UrasCycle]) -> tuple[UrasResult, ...]:
        """Drive successive stage-control values on adjacent cycles, without idle gaps."""

        self._require_started()
        results = []
        for transaction in transactions:
            event = await self.write_driver.send(
                CycleTransaction(self._cycle_values(transaction), cycles=0)
            )
            results.append(self.result_monitor.sample_at(event).value)
            self.reference.raise_failure()
        return tuple(results)

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("MicroRAS agent requires an active Execution")
        self.reference.raise_failure()
