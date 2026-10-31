"""suites.frontend.bpu.ras.agent.main components."""

from __future__ import annotations
import asyncio
from collections.abc import AsyncIterator
from collections.abc import Iterable
from contextlib import asynccontextmanager
from typing import Any
from toffee import Bundle
from toffee import ClockCycles
from toffee import Execution
from suites.frontend.bpu.drivers.signal import ClockedWriteDriver
from suites.frontend.bpu.drivers.signal import PulseDriver
from suites.frontend.bpu.drivers.signal import ResetDriver
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.ras.transaction.types import RasOperation
from suites.frontend.bpu.ras.bundle.ports import RasPorts
from suites.frontend.bpu.ras.transaction.types import RasState
from suites.frontend.bpu.ras.monitor.decode import _decode_state
from suites.frontend.bpu.ras.bundle.values import _plain
from suites.frontend.bpu.ras.driver.encoding import encode_cfi_pc
from suites.frontend.bpu.ras.checker.semantic import RasSemanticChecker
from suites.frontend.bpu.ras.monitor.semantic import RasSemanticMonitor
from suites.frontend.bpu.ras.coverage.semantic import RasActionCoverage
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT


_META_FIELDS = ('ssp', 'sctr', 'tosw', 'tosr', 'nos')


def _meta_ras(meta):
    """Project a public state snapshot onto the driven meta.ras leaves.

    The output redirectMeta additionally exposes the live top address, which
    is not an input leaf of meta.ras; a checkpoint snapshot can therefore not
    be fed back wholesale."""

    return {key: value for key, value in meta.items() if key in _META_FIELDS}


class RasAgent:
    def __init__(self, dut: Any) -> None:
        self.dut = dut
        self.ports = RasPorts.bind(dut)
        self.reset_driver = ResetDriver(dut)
        # Ras.scala gates every speculative/commit update on ``io.enable``;
        # the parent Bpu drives ``rasEnable``. This standalone adapter owns
        # that control pin like the other predictor agents.
        self.control_driver = ClockedWriteDriver(self.ports.control)
        self.spec_driver = PulseDriver(self.ports.speculative)
        self.redirect_driver = PulseDriver(self.ports.redirect)
        self.commit_driver = PulseDriver(self.ports.commit)
        self.state_monitor = CycleMonitor(
            self.ports.state, decoder=self._decode_state
        )
        self._started = False
        self._spec_lock = asyncio.Lock()
        self._execution: Execution | None = None
        self.semantic_coverage = RasActionCoverage()
        self.reference = RasSemanticChecker(coverage=self.semantic_coverage)
        self.reference_monitor = RasSemanticMonitor(dut, self.ports)

    async def start(self, execution: Execution) -> "RasAgent":
        if self._started:
            raise RuntimeError("RAS agent is already started")
        self.reference_monitor.start(execution, self.reference)
        await self.reset_driver.__aenter__()
        await self.control_driver.__aenter__()
        await self.spec_driver.__aenter__()
        await self.redirect_driver.__aenter__()
        await self.commit_driver.__aenter__()
        self._started = True
        self._execution = execution
        return self

    async def aclose(self) -> None:
        await self.reference_monitor.aclose()
        self.commit_driver.close()
        self.redirect_driver.close()
        self.spec_driver.close()
        self.control_driver.close()
        self.reset_driver.close()
        self._started = False
        self._execution = None
        self.semantic_coverage.write(output_directory(REPO_ROOT, 'ras'))
        self.reference.raise_unobserved_failure()

    async def reset(self, cycles: int = 3) -> None:
        self._require_started()
        await self.reset_driver.send(cycles)
        await self.control_driver.send({"enable": 1})
        status = self.ports.status.bits.sample()
        if not status.reset_done.as_int() or not status.train_ready.as_int():
            raise AssertionError("RAS did not become ready after reset")

    def snapshot(self) -> RasState:
        self._require_started()
        self.reference.raise_failure()
        return self._decode_state(self.ports.state.bits.sample())

    async def act(
        self,
        action: int,
        *,
        start_pc: int = 0,
        position: int = 0,
        enable: int = 1,
        branch_type: int | None = None,
    ) -> RasState:
        self._require_started()
        operation = RasOperation(action, start_pc, position, enable, branch_type)
        async with self._spec_lock:
            event = await self.spec_driver.send(operation.frame())
            self.reference.raise_failure()
            return self.state_monitor.sample_at(event).value

    async def act_many(self, operations: Iterable[RasOperation]) -> tuple[RasState, ...]:
        """Launch adjacent beats and return their aligned states in input order.

        Like act(), this waits for results, but there is no drain between beats.
        The public-state monitor is independent of optional native-memory observation.
        """

        self._require_started()
        operations = tuple(operations)
        if not operations or any(not isinstance(operation, RasOperation) for operation in operations):
            raise ValueError("act_many requires a non-empty sequence of RasOperation")
        # Start the passive monitor only after an earlier act()/act_many() has
        # drained, so concurrent agent calls cannot mix their observations.
        async with self._spec_lock:
            monitor = CycleMonitor(PortBinding(self.dut.clock, Bundle(
                speculative=Bundle(valid=self.ports.speculative.valid, bits=self.ports.speculative.bits),
                public=self.ports.state.bits,
            ), "ras.speculative_burst"), decoder=_plain)
            samples = []
            monitor.start(self._execution, observer=samples.append)
            try:
                await self.spec_driver.send_many(tuple(operation.frame() for operation in operations))
            finally:
                await monitor.aclose()
            accepted = [sample for sample in samples if sample.value["speculative"]["valid"]]
            self.reference.raise_failure()
            if len(samples) != len(operations) + 1 or len(accepted) != len(operations):
                raise AssertionError(
                    f"RAS burst alignment: operations={len(operations)}, samples={len(samples)}, "
                    f"accepted_ticks={[sample.event.tick for sample in accepted]}"
                )
            return tuple(RasState(**sample.value["public"]) for sample in samples[1:])

    async def restore(
        self, meta: Any, *, action: int = 0, cfi_pc: int = 0,
        branch_type: int | None = None,
    ) -> RasState:
        """Restore genuine checkpoint metadata and optionally redo its branch."""

        self._require_started()
        operation = RasOperation(action=action, branch_type=branch_type)
        encoded = encode_cfi_pc(cfi_pc)
        await self.redirect_driver.send(
            {
                "action": action,
                "meta": _meta_ras(meta),
                "cfi_pc": encoded,
            }
        )
        event = await ClockCycles(self.dut.clock, 1)
        self.reference.raise_failure()
        return self.state_monitor.sample_at(event).value

    async def recover(
        self, meta: Any, *, action: int, cfi_pc: int = 0,
        branch_type: int | None = None,
    ) -> RasState:
        return await self.restore(meta, action=action, cfi_pc=cfi_pc, branch_type=branch_type)

    @asynccontextmanager
    async def observe_committed(self) -> AsyncIterator[list[Any]]:
        """Capture committed cells and pipeline activity via memory-direct."""

        from suites.frontend.bpu.ras.monitor.observation import RasCommittedMonitor

        self._require_started()
        monitor = RasCommittedMonitor(self)
        observations = []
        monitor.start(self._execution, observer=observations.append)
        try:
            yield observations
        finally:
            await monitor.aclose()

    async def commit(
        self, meta: Any, *, action: int, branch_type: int | None = None,
    ) -> RasState:
        """Retire a branch with its pre-operation commit metadata.

        RAS registers commit before updating its committed stack. Keep that
        latency here; a testcase supplies a branch operation, not edge timing.
        """

        self._require_started()
        operation = RasOperation(action=action, branch_type=branch_type)
        await self.commit_driver.send(
            {
                "action": action,
                "meta": _meta_ras(meta),
            }
        )
        event = await ClockCycles(self.dut.clock, 1)
        self.reference.raise_failure()
        return self.state_monitor.sample_at(event).value

    _decode_state = staticmethod(_decode_state)

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("RAS agent requires an active Execution")
