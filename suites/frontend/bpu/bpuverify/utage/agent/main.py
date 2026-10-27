"""bpuverify.utage.agent.main components."""

from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from typing import Any
from typing import AsyncIterator
from typing import Sequence
from toffee import Bundle
from toffee import CheckContext, ScoreboardMode
from toffee import ClockCycles
from bpuverify.common.monitor.activity import ActivityMonitor
from bpuverify.utage.bundle.activity import training_activity
from bpuverify.common.env.wait import wait_reset_done
from toffee import Execution
from toffee import MISSING
from toffee import Scoreboard
from toffee import Transfer
from toffee import XTransfer
from toffee.signals import signal_width
from bpuverify.common.checker.prediction import compare_prediction
from bpuverify.utage.checker.semantic import UtageSemanticChecker
from bpuverify.utage.monitor.semantic import UtageSemanticMonitor
from bpuverify.common.driver.signal import AsyncSingleCycleDriver
from bpuverify.common.driver.signal import ClockedWriteDriver
from bpuverify.common.driver.signal import PulseDriver
from bpuverify.common.driver.signal import ResetDriver
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.monitor.cycle import CycleMonitor
from bpuverify.common.model.folded_history import folded_history_values
from bpuverify.common.model.folded_history import validate_folded_history_layout
from bpuverify.utage.transaction.types import UtageBaseBranch
from bpuverify.utage.transaction.types import UtageLookup
from bpuverify.utage.bundle.ports import UtagePorts
from bpuverify.utage.transaction.types import UtagePrediction
from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.driver.encoding import _ahead_btb
from bpuverify.utage.monitor.decode import _decode
from bpuverify.utage.driver.encoding import encode_training


class UtageAgent:
    def __init__(self, dut: Any) -> None:
        self.dut = dut
        self.ports = UtagePorts.bind(dut)
        self.training_activity = ActivityMonitor(training_activity(dut))
        self._abtb_capacity = len(self.ports.lookup.bits.ahead_btb.result)
        self._history_count = len(self.ports.lookup.bits.normal_history)
        if any(
            len(self.ports.lookup.bits[name]) != self._history_count
            for name in ("s1_history", "override_history")
        ):
            raise ValueError("MicroTAGE folded-history ports differ in shape")
        for name in ("normal_history", "s1_history", "override_history"):
            validate_folded_history_layout(
                signal_width(field.foldedHist) for field in self.ports.lookup.bits[name]
            )
        self._last_a0_lookup: UtageLookup | None = None
        self.reset_driver = ResetDriver(dut)
        self.control_driver = ClockedWriteDriver(self.ports.control)
        lookup = self.ports.lookup.bits
        fast_lookup = PortBinding(
            dut.clock,
            Bundle(
                s0_fire=lookup.s0_fire,
                s2_fire=lookup.s2_fire,
                s2_override=lookup.s2_override,
                s3_override=lookup.s3_override,
                start_pc=lookup.start_pc,
                new_start_pc=lookup.new_start_pc,
                override_start_pc=lookup.override_start_pc,
                redirect=lookup.redirect,
                normal_history=lookup.normal_history,
                s1_history=lookup.s1_history,
                override_history=lookup.override_history,
                ahead_btb=Bundle(fastPositions=lookup.ahead_btb.fastPositions),
            ),
            "utage.lookup_fast",
        )
        self.lookup_driver = AsyncSingleCycleDriver(
            fast_lookup,
            idle=lambda request: {
                "s0_fire": int(request is not None),
                "s2_fire": int(request is not None),
                "s2_override": 0,
                "s3_override": 0,
                "start_pc": 0 if request is None else request.read_pc,
                "new_start_pc": 0 if request is None else request.pc,
                "override_start_pc": 0 if request is None else request.pc,
                "redirect": 0,
                "normal_history": folded_history_values(
                    0 if request is None else request.read_history,
                    self._history_count,
                ),
                "s1_history": folded_history_values(
                    0 if request is None else request.folded_history,
                    self._history_count,
                ),
                "override_history": folded_history_values(
                    0 if request is None else request.folded_history,
                    self._history_count,
                ),
                "ahead_btb": {
                    "fastPositions": self._ahead_btb(None if request is None else request)["fastPositions"],
                },
            },
            encoder=self._encode_lookup,
        )
        idle_result = tuple(
            {**entry, "valid": 0}
            for entry in self._ahead_btb(None)["result"]
        )
        self.result_driver = AsyncSingleCycleDriver(
            PortBinding(dut.clock, lookup.ahead_btb.result, "utage.abtb_result"),
            idle=idle_result,
            encoder=lambda request: self._ahead_btb(request)["result"],
        )
        self._result_tasks: set[asyncio.Task[None]] = set()
        self.training_driver = PulseDriver(self.ports.training)
        self.training_observations: list[Transfer[Any]] = []
        self.training_monitor = CycleMonitor(PortBinding(
            dut.clock,
            Bundle(valid=self.ports.training.valid,
                   pc=self.ports.training.bits.start_pc,
                   read_index=self.ports.training.bits.meta.readIndex),
            "utage.feedback",
        ))
        self.monitor = CycleMonitor(self.ports.prediction, decoder=self._decode)
        self.reference = UtageSemanticChecker()
        self.reference_monitor = UtageSemanticMonitor(self)
        self.prediction_scoreboard = Scoreboard(
            "utage.prediction",
            compare=compare_prediction,
            expected=self.reference.response_expected,
        )
        self._execution: Execution | None = None

    async def start(self, execution: Execution) -> "UtageAgent":
        self._execution = execution
        self.reference_monitor.start(execution, self.reference)
        await self.reset_driver.__aenter__()
        await self.control_driver.__aenter__()
        self.lookup_driver.start(execution)
        self.result_driver.start(execution)
        self.prediction_scoreboard.bind(
            execution,
            driver=self.lookup_driver,
            monitor=self.monitor,
            clock=self.dut.clock,
            response_timeout_cycles=64,
            latency_cycles=2,
            sampled=True,
        )
        await self.training_driver.__aenter__()
        self.training_monitor.start(execution, observer=self._observe_training)
        await self.set_enabled(True)
        return self

    async def aclose(self) -> None:
        try:
            await self.training_monitor.aclose()
            await self.prediction_scoreboard.aclose()
            await self._drain_result_tasks()
        finally:
            await self.reference_monitor.aclose()
            self.training_driver.close()
            await self.lookup_driver.aclose()
            await self.result_driver.aclose()
            self.control_driver.close()
            self.reset_driver.close()
            self._execution = None
        self.reference.raise_unobserved_failure()

    async def reset(self, cycles: int = 3) -> int:
        await self._drain_result_tasks()
        self.lookup_driver.quiesce()
        self.result_driver.quiesce()
        self._last_a0_lookup = None
        await self.reset_driver.send(cycles)
        self.training_observations.clear()
        await self.set_enabled(True)
        waited = (await wait_reset_done(self.ports.status)).samples
        if not self.ports.status.bits.sample().train_ready.as_int():
            raise AssertionError("MicroTAGE training port is not ready")
        return waited

    @asynccontextmanager
    async def observe_useful(self, checker: Any) -> AsyncIterator[Any]:
        """Compare every useful update and hand the first failure to the caller."""
        from bpuverify.utage.env.observation import observe_useful

        async with observe_useful(self, observer=checker.capture) as monitor:
            yield monitor
            checker.raise_failure()

    def observe_shadow(self, *, table: int):
        """Capture retained shadow cells and priority response through a Bundle."""
        from bpuverify.utage.env.shadow import observe_shadow

        return observe_shadow(self, table=table)

    def observe_partial_wrap(self, checker: Any):
        """Observe and compare a bounded partial-wrap reference safely."""
        from bpuverify.utage.env.partial_wrap import observe_partial_wrap

        return observe_partial_wrap(self, checker)

    def _observe_training(self, observation) -> None:
        if observation.value.valid.as_int():
            self.training_observations.append(observation)

    async def set_enabled(self, enabled: bool) -> None:
        """Control the global prediction/fastTrain gate independently."""

        await self._drain_result_tasks()
        self.lookup_driver.quiesce()
        self.result_driver.quiesce()
        self._last_a0_lookup = None
        await self.control_driver.send({"enable": int(enabled)})

    def _encode_lookup(self, request: UtageLookup) -> dict[str, Any]:
        # A0 reads the SRAM using the new request. The A1 tag/position inputs
        # belong to the A0 request accepted on the preceding cycle.
        previous = self._last_a0_lookup or request
        self._last_a0_lookup = request
        return {
            "s0_fire": 1,
            "s2_fire": 1,
            "s2_override": int(request.override == "s2"),
            "s3_override": int(request.override == "s3"),
            "start_pc": request.read_pc,
            "new_start_pc": previous.pc,
            "override_start_pc": request.pc if request.override_pc is None else request.override_pc,
            "redirect": int(request.redirect),
            "normal_history": folded_history_values(request.read_history, self._history_count),
            "s1_history": folded_history_values(previous.folded_history, self._history_count),
            "override_history": folded_history_values(request.folded_history, self._history_count),
            "ahead_btb": {"fastPositions": self._ahead_btb(previous)["fastPositions"]},
        }

    def _ahead_btb(self, request: UtageLookup | None) -> dict[str, Any]:
        if request is None:
            return _ahead_btb(0, 0, capacity=self._abtb_capacity)
        return _ahead_btb(
            request.position,
            request.base_taken,
            request.branches,
            capacity=self._abtb_capacity,
        )

    def submit_predict(
        self,
        pc: int,
        position: int,
        base_taken: int,
        *,
        override: str | None = None,
        override_pc: int | None = None,
        folded_history: int = 0,
        branches: Sequence[UtageBaseBranch | None] | None = None,
        index_pc: int | None = None,
        index_history: int | None = None,
        redirect: bool = False,
        expected: Any = MISSING,
    ) -> XTransfer[UtageLookup, UtagePrediction]:
        if override not in (None, "s2", "s3"):
            raise ValueError(f"unknown MicroTAGE override stage: {override!r}")
        if type(redirect) is not bool:
            raise ValueError("MicroTAGE redirect must be an explicit bool")
        request = UtageLookup(
            pc, position, base_taken, override, override_pc, folded_history,
            None if branches is None else tuple(branches),
            index_pc=index_pc, index_history=index_history, redirect=redirect,
        )
        self._ahead_btb(request)
        folded_history_values(folded_history, self._history_count)
        folded_history_values(request.read_history, self._history_count)
        transfer = self.prediction_scoreboard.submit(
            request,
            expected=expected,
        )
        task = asyncio.create_task(self._drive_a2_result(transfer))
        self._result_tasks.add(task)
        return transfer

    async def _drive_a2_result(self, transfer: XTransfer[UtageLookup, UtagePrediction]) -> None:
        await transfer.wait_processing()
        await ClockCycles(self.dut.clock, 1)
        await self.result_driver.send(transfer.request)

    async def _drain_result_tasks(self) -> None:
        failures = []
        while self._result_tasks:
            task = next(iter(self._result_tasks))
            try:
                await task
            except Exception as error:
                failures.append(error)
            finally:
                self._result_tasks.discard(task)
        # Retrieve every task, including tasks aborted by a scoreboard failure.
        # The already-delivered reference exception must remain one pytest
        # FAIL, not an additional teardown ERROR or an unhandled task warning.
        for error in failures:
            if error is self.reference.failure and self.reference.failure_observed:
                continue
            raise error

    def submit_predict_branches(
        self,
        pc: int,
        branches: Sequence[UtageBaseBranch | None],
        *,
        folded_history: int = 0,
        index_pc: int | None = None,
        index_history: int | None = None,
        override: str | None = None,
        override_pc: int | None = None,
        expected: Any = MISSING,
    ) -> XTransfer[UtageLookup, UtagePrediction]:
        """Issue one lookup containing multiple ordered AheadBTB slots.

        A recovery presents the same AheadBTB beat it was originally resolved
        with; the saved vector, not a re-derived single-branch read, must decide
        which slot/table payload is replayed.
        """

        return self.submit_predict(
            pc, 0, 0, folded_history=folded_history,
            branches=branches, expected=expected, override=override,
            override_pc=override_pc, index_pc=index_pc, index_history=index_history,
        )

    async def predict_branches(
        self,
        pc: int,
        branches: Sequence[UtageBaseBranch | None],
        *,
        folded_history: int = 0,
        index_pc: int | None = None,
        index_history: int | None = None,
    ) -> UtagePrediction:
        actual = await self.submit_predict_branches(
            pc, branches, folded_history=folded_history,
            index_pc=index_pc, index_history=index_history,
        )
        self.reference.raise_failure()
        return actual

    async def recover_prediction_branches(
        self,
        pc: int,
        branches: Sequence[UtageBaseBranch | None],
        *,
        stage: str,
        override_pc: int,
    ) -> UtagePrediction:
        """Observe a multi-branch recovery one cycle after input acceptance."""

        transfer = self.submit_predict_branches(
            pc, branches, override=stage, override_pc=override_pc)
        await transfer.wait_processing()
        event = await ClockCycles(self.dut.clock, 1)
        observed = self.monitor.sample_at(event).value
        await transfer
        self.reference.raise_failure()
        return observed

    async def drain_predictions(self):
        result = await self.prediction_scoreboard.drain(timeout_cycles=64)
        await self._drain_result_tasks()
        self.reference.raise_failure()
        return result

    async def predict(
        self,
        pc: int,
        position: int,
        base_taken: int,
        *,
        override: str | None = None,
        override_pc: int | None = None,
        folded_history: int = 0,
        index_pc: int | None = None,
        index_history: int | None = None,
    ) -> UtagePrediction:
        actual = await self.submit_predict(
            pc, position, base_taken, override=override, override_pc=override_pc,
            folded_history=folded_history,
            index_pc=index_pc, index_history=index_history,
        )
        self.reference.raise_failure()
        return actual

    async def recover_prediction(
        self,
        pc: int,
        position: int,
        base_taken: int,
        *,
        stage: str,
        override_pc: int,
    ) -> UtagePrediction:
        """Observe the override result one cycle after input acceptance."""

        transfer = self.submit_predict(
            pc, position, base_taken, override=stage, override_pc=override_pc
        )
        await transfer.wait_processing()
        event = await ClockCycles(self.dut.clock, 1)
        observed = self.monitor.sample_at(event).value
        await transfer
        self.reference.raise_failure()
        return observed

    encode_training = staticmethod(encode_training)

    async def train(self, transaction: UtageTraining) -> None:
        await self.train_many((transaction,))

    def allow_known_miss(self, pc: int, position: int, reason: str) -> None:
        """Declare one known tag-width miss; every use is recorded."""
        self.reference.allow_known_miss(pc, position, reason)

    def allow_known_counter_difference(self, table: int, index: int, reason: str) -> None:
        """Declare one known persistence cell; only its counter field is allowed."""
        self.reference.allow_known_counter_difference(table, index, reason)

    @property
    def allowed_reference_events(self):
        return tuple(self.reference.allowed_events)

    def check_useful(self, table: int, index: int, expected: int) -> None:
        """Check a semantic endpoint against owned state and read-only actual."""
        self.reference.raise_failure()
        actual = self.reference_monitor.read_useful(table, index)
        self.reference.board.check(expected=(expected, expected),
            actual=(self.reference.model.useful[table].get(index, 0), actual),
            context=CheckContext(self.reference.board.name, ScoreboardMode.DIRECT,
                request=dict(table=table, index=index, endpoint=expected),
                observed_event=self.reference.last_event))

    async def train_many(self, transactions: Sequence[UtageTraining]) -> None:
        """Send adjacent fastTrain beats, then wait once for the final update.

        Prediction reads may remain active. PulseDriver owns every launch;
        neither the test nor this adapter handles clock edges or bare signals.
        """

        if not transactions:
            raise ValueError("MicroTAGE feedback burst must not be empty")
        encoded = tuple(self.encode_training(transaction) for transaction in transactions)
        await self.training_driver.send_many(encoded)
        # Prediction may continue to read the same single-port bank. Retire
        # feedback into the forwarding shadow buffer, not necessarily SRAM.
        await self.training_activity.wait_idle('pipeline')
        self.reference.raise_failure()

    _decode = staticmethod(_decode)
