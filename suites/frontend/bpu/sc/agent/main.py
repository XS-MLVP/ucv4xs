"""suites.frontend.bpu.sc.agent.main components."""

from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Any
from typing import Sequence
from toffee import AsyncMultiCycleDriver
from toffee import Bundle
from toffee import CheckContext
from toffee import ClockCycles
from suites.frontend.bpu.monitors.activity import ActivityMonitor
from suites.frontend.bpu.sc.bundle.activity import training_activity
from suites.frontend.bpu.runtime.wait import wait_reset_done
from toffee import DriveStage
from toffee import Execution
from toffee import MISSING
from toffee import Scoreboard
from toffee import ScoreboardMode
from toffee import XTransfer
from suites.frontend.bpu.checkers.prediction import compare_prediction
from suites.frontend.bpu.sc.checker.semantic import ScSemanticChecker
from suites.frontend.bpu.sc.monitor.semantic import ScSemanticMonitor
from suites.frontend.bpu.drivers.signal import ClockedWriteDriver
from suites.frontend.bpu.drivers.signal import PulseDriver
from suites.frontend.bpu.drivers.signal import ResetDriver
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.sc.monitor.threshold import ScThresholdMonitor
from suites.frontend.bpu.sc.monitor.feedback import ScFeedbackMonitor
from suites.frontend.bpu.sc.transaction.types import ScBaseBranch
from suites.frontend.bpu.sc.transaction.types import ScBatchTraining
from suites.frontend.bpu.sc.transaction.types import ScBranchFeedback
from suites.frontend.bpu.sc.transaction.types import ScLookup
from suites.frontend.bpu.sc.bundle.ports import ScPorts
from suites.frontend.bpu.sc.transaction.types import ScPrediction
from suites.frontend.bpu.sc.transaction.types import ScTraining
from suites.frontend.bpu.sc.transaction.types import ScHistory
from suites.frontend.bpu.sc.driver.encoding import _mbtb_meta_branches
from suites.frontend.bpu.sc.driver.encoding import _mbtb_result
from suites.frontend.bpu.sc.bundle.values import _plain
from suites.frontend.bpu.sc.driver.encoding import _provider_counters
from suites.frontend.bpu.sc.driver.encoding import _sc_s2_context
from suites.frontend.bpu.sc.driver.encoding import encode_history
from suites.frontend.bpu.models.folded_history import PHR_FOLD_LAYOUT
from suites.frontend.bpu.sc.coverage.semantic import ScHistoryCoverage
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT


class ScAgent:
    def __init__(self, dut: Any) -> None:
        self.dut = dut
        self.ports = ScPorts.bind(dut)
        self.training_activity = ActivityMonitor(training_activity(dut))
        self._branch_capacity = len(self.ports.lookup.bits.mbtb_result)
        self.reset_driver = ResetDriver(dut)
        self.control_driver = ClockedWriteDriver(self.ports.control)
        lookup = self.ports.lookup.bits
        self._history_indices = self.ports.history_indices
        widths = tuple(signal.foldedHist.mWidth for signal in lookup.path_history)
        expected = tuple(PHR_FOLD_LAYOUT[index][1] for index in self._history_indices)
        if widths != expected:
            raise ValueError(
                f"sparse SC history layout differs from DefaultConfig: {widths}, expected {expected}")
        self.lookup_driver = AsyncMultiCycleDriver(
            self.ports.lookup.clock,
            (
                DriveStage(
                    "sc.s0",
                    Bundle(
                        fire=lookup.s0_fire,
                        start_pc=lookup.start_pc,
                        common_hr_valid=lookup.common_hr_valid,
                        global_history=lookup.global_history,
                        backward=lookup.backward,
                        loop=lookup.loop,
                        path_history=lookup.path_history,
                    ),
                    {"fire": 0, "start_pc": 0, **encode_history(
                        ScHistory(common_valid=False), self._history_indices)},
                    self._encode_s0,
                ),
                DriveStage("sc.s1", lookup.s1_fire, 0, lambda request: 1),
                DriveStage(
                    "sc.s2",
                    Bundle(
                        fire=lookup.s2_fire,
                        mbtb_result=lookup.mbtb_result,
                        provider_counters=lookup.provider_counters,
                    ),
                    {
                        "fire": 0,
                        "mbtb_result": _mbtb_result(0, 0, 0),
                        "provider_counters": _provider_counters(0, 0),
                    },
                    self._encode_s2,
                ),
            ),
            name=self.ports.lookup.name,
            max_active=3,
        )
        self.training_driver = PulseDriver(self.ports.training)
        self.training_observations: list[Any] = []
        self.training_monitor = CycleMonitor(PortBinding(
            dut.clock,
            Bundle(
                valid=self.ports.training.valid,
                pc=self.ports.training.bits.start_pc,
                selectors=self.ports.training.bits.sc_meta.scBiasLowerBits,
                branches=self.ports.training.bits.branches,
            ),
            "sc.feedback",
        ))
        self._prior_decision = (
            (0,) * self._branch_capacity,
            (0,) * self._branch_capacity,
        )
        self.monitor = CycleMonitor(self.ports.prediction, decoder=self._decode)
        self.semantic_coverage = ScHistoryCoverage()
        self.reference = ScSemanticChecker(coverage=self.semantic_coverage)
        self.reference_monitor = ScSemanticMonitor(dut, self.ports)
        self.prediction_scoreboard = Scoreboard(
            "sc.prediction",
            compare=compare_prediction,
            expected=self.reference.response_expected,
        )
        self._execution: Execution | None = None
        self._threshold_monitor: ScThresholdMonitor | None = None
        self._feedback_monitor = None
        self._feedback_observing = False
        self.threshold_scoreboard = Scoreboard('sc.thresholds')

    async def start(self, execution: Execution) -> "ScAgent":
        self._execution = execution
        self.reference_monitor.start(execution, self.reference)
        await self.reset_driver.__aenter__()
        await self.control_driver.__aenter__()
        self.lookup_driver.start(execution)
        self.prediction_scoreboard.bind(
            execution,
            driver=self.lookup_driver,
            monitor=self.monitor,
            clock=self.dut.clock,
            response_timeout_cycles=64,
            latency_cycles=1,
            sampled=True,
        )
        await self.training_driver.__aenter__()
        self.training_monitor.start(execution, observer=self._observe_training)
        await self.set_enabled(True)
        return self

    async def aclose(self) -> None:
        try:
            if self._feedback_monitor is not None:
                await self._feedback_monitor.aclose()
            if self._threshold_monitor is not None:
                await self._threshold_monitor.aclose()
            await self.training_monitor.aclose()
            await self.prediction_scoreboard.aclose()
        finally:
            await self.reference_monitor.aclose()
            self.training_driver.close()
            await self.lookup_driver.aclose()
            self.control_driver.close()
            self.reset_driver.close()
            self._execution = None
            self.semantic_coverage.write(output_directory(REPO_ROOT, 'sc'))
        self.reference.raise_unobserved_failure()

    async def reset(self, cycles: int = 3) -> int:
        await self.reset_driver.send(cycles)
        self.training_observations.clear()
        await self.set_enabled(True)
        return (await wait_reset_done(self.ports.status)).samples

    def _observe_training(self, observation) -> None:
        if observation.value.valid.as_int():
            self.training_observations.append(observation)

    async def set_enabled(self, enabled: bool) -> None:
        """Hold the SC global lookup/training gate independently of requests."""

        await self.control_driver.send({"enable": int(enabled)})

    async def _threshold_observation(self):
        if self._execution is None:
            raise RuntimeError('SC threshold observation requires an active agent')
        if self._threshold_monitor is None:
            self._threshold_monitor = ScThresholdMonitor(self.dut)
        return await self._threshold_monitor.read(self._execution)

    async def read_thresholds(self) -> tuple[int, ...]:
        return (await self._threshold_observation()).value

    async def check_thresholds(self, expected, *, request=None) -> None:
        observation = await self._threshold_observation()
        accepted = self.training_observations[-1].event if request is not None and self.training_observations else None
        self.threshold_scoreboard.check(
            expected=tuple(expected), actual=observation.value,
            context=CheckContext(
                scoreboard='sc.thresholds', mode=ScoreboardMode.DIRECT,
                sequence_id=len(self.training_observations), request=request,
                accepted_event=accepted, observed_event=observation.event,
            ),
        )

    def submit_predict(
        self,
        pc: int,
        position: int,
        tage_counter: int,
        *,
        provider_valid: int = 1,
        mbtb_valid: int = 1,
        branch_type: int = 1,
        branches: Sequence[ScBaseBranch | None] | None = None,
        history: ScHistory = ScHistory(),
        expected: Any = MISSING,
    ) -> XTransfer[ScLookup, ScPrediction]:
        request = ScLookup(
            pc, position, tage_counter, provider_valid, mbtb_valid, branch_type,
            None if branches is None else tuple(branches),
            history,
        )
        _sc_s2_context(request, self._branch_capacity)
        return self.prediction_scoreboard.submit(
            request,
            expected=expected,
        )

    def submit_predict_branches(
        self,
        pc: int,
        branches: Sequence[ScBaseBranch | None],
        *,
        history: ScHistory = ScHistory(),
        expected: Any = MISSING,
    ) -> XTransfer[ScLookup, ScPrediction]:
        return self.submit_predict(pc, 0, 0, branches=branches, history=history, expected=expected)

    async def predict_branches(
        self,
        pc: int,
        branches: Sequence[ScBaseBranch | None],
        *, history: ScHistory = ScHistory(),
    ) -> ScPrediction:
        actual = await self.submit_predict_branches(pc, branches, history=history)
        self.reference.raise_failure()
        return actual

    async def drain_predictions(self):
        status = await self.prediction_scoreboard.drain(timeout_cycles=64)
        self.reference.raise_failure()
        return status

    async def predict(
        self,
        pc: int,
        position: int,
        tage_counter: int,
        *,
        provider_valid: int = 1,
        mbtb_valid: int = 1,
        branch_type: int = 1,
        history: ScHistory = ScHistory(),
    ) -> ScPrediction:
        actual = await self.submit_predict(
            pc,
            position,
            tage_counter,
            provider_valid=provider_valid,
            mbtb_valid=mbtb_valid,
            branch_type=branch_type,
            history=history,
        )
        self.reference.raise_failure()
        return actual

    async def train(self, transaction: ScTraining) -> None:
        await self.train_batch(
            ScBatchTraining(
                transaction.pc,
                transaction.meta,
                (ScBranchFeedback(
                    transaction.position,
                    transaction.actual_taken,
                    prediction_slot=0,
                    mbtb_hit=transaction.mbtb_hit,
                    branch_type=transaction.branch_type,
                ),),
                transaction.history,
            )
        )

    async def train_batch(self, transaction: ScBatchTraining) -> None:
        await self.training_driver.send(self._encode_batch_training(transaction))
        await self.training_activity.wait_idle()
        self.reference.raise_failure()

    @asynccontextmanager
    async def observe_feedback(self):
        """Opt-in immutable input beats; callers never sample pins or edges."""
        if self._execution is None or self._feedback_observing:
            raise RuntimeError('complete SC feedback observation needs an active, unoccupied agent')
        if self._feedback_monitor is None:
            self._feedback_monitor = ScFeedbackMonitor(self.ports)
        frames = []
        self._feedback_observing = True
        try:
            self._feedback_monitor.start(self._execution, observer=lambda frame:
                frames.append(frame) if frame.value['valid'] else None)
            yield frames
        finally:
            try:
                await self._feedback_monitor.aclose()
            finally:
                self._feedback_observing = False

    async def train_batches(self, transactions: Sequence[ScBatchTraining]) -> None:
        """Send FTQ feedback on adjacent cycles, then wait for SC writes to retire."""

        if not transactions:
            raise ValueError("SC feedback burst must not be empty")
        await self.training_driver.send_many(
            tuple(self._encode_batch_training(transaction) for transaction in transactions)
        )
        await self.training_activity.wait_idle()
        self.reference.raise_failure()

    def _encode_batch_training(self, transaction: ScBatchTraining) -> dict[str, Any]:
        branch_count = len(self.ports.training.bits.branches)
        if not 1 <= len(transaction.branches) <= branch_count:
            raise ValueError(f"SC feedback requires 1 to {branch_count} branch slots")
        active = [branch for branch in transaction.branches if branch is not None]
        if not active:
            raise ValueError("SC feedback requires at least one valid branch")
        mbtb_meta = self.ports.training.bits.mbtb_meta
        banks = len(mbtb_meta)
        entries_per_bank = len(mbtb_meta[0])
        capacity = banks * entries_per_bank
        if any(not 0 <= branch.prediction_slot < capacity for branch in active):
            raise ValueError(f"SC prediction slots must be in 0..{capacity - 1}")
        if len({branch.prediction_slot for branch in active}) != len(active):
            raise ValueError("SC feedback prediction slots must be distinct")
        if len({branch.position for branch in active}) != len(active):
            raise ValueError("SC feedback branch positions must be distinct")
        padded = transaction.branches + (None,) * (branch_count - len(transaction.branches))
        return {
            "start_pc": transaction.pc,
            **encode_history(transaction.history, getattr(self, '_history_indices', None)),
            "mbtb_meta": _mbtb_meta_branches(
                active, banks=banks, entries_per_bank=entries_per_bank,
            ),
            "sc_meta": transaction.meta,
            "branches": tuple(
                {
                    "valid": int(branch is not None),
                    "taken": 0 if branch is None else branch.actual_taken,
                    "position": 0 if branch is None else branch.position,
                    "branch_type": 0 if branch is None else branch.branch_type,
                }
                for branch in padded
            ),
        }

    def _encode_s0(self, request: ScLookup) -> dict[str, Any]:
        return {
            "fire": 1,
            "start_pc": request.pc,
            **encode_history(request.history, getattr(self, '_history_indices', None)),
        }

    def _encode_s2(self, request: ScLookup) -> dict[str, Any]:
        return {
            "fire": 1,
            **_sc_s2_context(request, self._branch_capacity),
        }

    def _decode(self, sample: Any) -> ScPrediction:
        # SC's decision is combinational in S2; its metadata is registered by
        # s2_fire and becomes observable one cycle later. Pair that metadata
        # with the previous cycle's decision before publishing a transaction.
        takens, useds = self._prior_decision
        self._prior_decision = (
            tuple(value.as_int() for value in sample.takens),
            tuple(value.as_int() for value in sample.useds),
        )
        return ScPrediction(takens[0], useds[0], _plain(sample.meta), takens, useds)
