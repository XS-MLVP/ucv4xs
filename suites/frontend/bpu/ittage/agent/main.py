"""suites.frontend.bpu.ittage.agent.main components."""

from __future__ import annotations
from typing import Any
from typing import Sequence
from toffee import ClockCycles
from suites.frontend.bpu.monitors.activity import ActivityMonitor
from suites.frontend.bpu.ittage.bundle.activity import training_activity
from suites.frontend.bpu.runtime.wait import wait_reset_done
from toffee import Execution
from toffee import MISSING
from toffee import Scoreboard
from toffee import XEvent
from toffee import XTransfer
from toffee.signals import signal_width
from suites.frontend.bpu.checkers.prediction import compare_prediction
from suites.frontend.bpu.drivers.signal import AsyncSingleCycleDriver
from suites.frontend.bpu.drivers.signal import ClockedWriteDriver
from suites.frontend.bpu.drivers.signal import PulseDriver
from suites.frontend.bpu.drivers.signal import ResetDriver
from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.models.folded_history import PHR_FOLD_LAYOUT, folded_history_values
from suites.frontend.bpu.models.folded_history import validate_folded_history_layout
from suites.frontend.bpu.models.address import encode_pruned_pc
from suites.frontend.bpu.ittage.transaction.types import IttageBatchTraining
from suites.frontend.bpu.ittage.transaction.types import IttageBranchFeedback
from suites.frontend.bpu.ittage.transaction.types import IttageLookup
from suites.frontend.bpu.ittage.bundle.ports import IttagePorts
from suites.frontend.bpu.ittage.transaction.types import IttagePrediction
from suites.frontend.bpu.ittage.transaction.types import IttageTraining
from suites.frontend.bpu.ittage.monitor.decode import _decode
from suites.frontend.bpu.ittage.driver.encoding import _encode_branch_feedback
from suites.frontend.bpu.ittage.checker.semantic import IttageSemanticChecker
from suites.frontend.bpu.ittage.monitor.semantic import IttageSemanticMonitor
from suites.frontend.bpu.ittage.coverage.semantic import TargetLearningCoverage
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT


class IttageAgent:
    def __init__(self, dut: Any) -> None:
        self.dut = dut
        self.ports = IttagePorts.bind(dut)
        self.training_activity = ActivityMonitor(training_activity(dut))
        self._history_count = len(self.ports.lookup.bits.folded_history)
        self._history_indices = self.ports.history_indices
        for history in (self.ports.lookup.bits.folded_history, self.ports.training.bits.folded_history):
            widths = tuple(signal_width(field.foldedHist) for field in history)
            expected = tuple(PHR_FOLD_LAYOUT[index][1] for index in self._history_indices)
            if widths != expected:
                raise ValueError(
                    f"sparse ITTAGE history layout differs from DefaultConfig: {widths}, expected {expected}")
        self._last_a0_lookup: IttageLookup | None = None
        self.reset_driver = ResetDriver(dut)
        self.control_driver = ClockedWriteDriver(self.ports.control)
        self.lookup_driver = AsyncSingleCycleDriver(
            self.ports.lookup,
            idle=lambda request: {
                "s0_fire": 0,
                "s1_fire": 0 if request is None else 1,
                "s2_fire": 0 if request is None else 1,
                "s3_fire": 0 if request is None else 1,
                "start_pc": 0 if request is None else encode_pruned_pc(request.pc),
                "folded_history": self._history_values(
                    0 if request is None else request.folded_history),
            },
            encoder=self._encode_lookup,
        )
        self.training_driver = PulseDriver(self.ports.training)
        self.prediction_monitor = CycleMonitor(
            self.ports.prediction, decoder=self._decode
        )
        self.reference_coverage = TargetLearningCoverage()
        self.reference = IttageSemanticChecker(coverage=self.reference_coverage)
        self.reference_monitor = IttageSemanticMonitor(dut, self.ports)
        self.prediction_scoreboard = Scoreboard(
            "ittage.prediction",
            compare=compare_prediction,
            expected=self.reference.response_expected,
        )
        self._execution: Execution | None = None
        self._started = False

    async def start(self, execution: Execution) -> "IttageAgent":
        self._execution = execution
        await self.reset_driver.__aenter__()
        await self.control_driver.__aenter__()
        self.reference_monitor.start(execution, self.reference)
        self.lookup_driver.start(execution)
        self.prediction_scoreboard.bind(
            execution,
            driver=self.lookup_driver,
            monitor=self.prediction_monitor,
            clock=self.dut.clock,
            response_timeout_cycles=64,
            latency_cycles=3,
            sampled=True,
        )
        await self.training_driver.__aenter__()
        self._started = True
        await self.set_enabled(True)
        return self

    async def aclose(self) -> None:
        try:
            await self.prediction_scoreboard.aclose()
        finally:
            await self.reference_monitor.aclose()
            self.training_driver.close()
            await self.lookup_driver.aclose()
            self.control_driver.close()
            self.reset_driver.close()
            self._execution = None
            self._started = False
            self.reference_coverage.write(output_directory(REPO_ROOT, 'ittage'))
        self.reference.raise_unobserved_failure()

    async def reset(self, cycles: int = 3) -> int:
        self._require_started()
        self.lookup_driver.quiesce()
        self._last_a0_lookup = None
        await self.reset_driver.send(cycles)
        await self.set_enabled(True)
        return (await wait_reset_done(self.ports.status)).samples

    async def set_enabled(self, enabled: bool) -> None:
        """Hold the global lookup/training gate independently of requests."""

        self._require_started()
        self.lookup_driver.quiesce()
        self._last_a0_lookup = None
        await self.control_driver.send({"enable": int(enabled)})

    def _history_values(self, history: int):
        rows = folded_history_values(history, len(PHR_FOLD_LAYOUT))
        return tuple(rows[index] for index in self._history_indices)

    def _encode_lookup(self, request: IttageLookup) -> dict[str, Any]:
        # The input PC enters S0, while folded history is consumed with that
        # PC in S1 on the next cycle. Adjacent requests need different values.
        previous = self._last_a0_lookup or request
        self._last_a0_lookup = request
        return {
            "s0_fire": 1,
            "s1_fire": 1,
            "s2_fire": 1,
            "s3_fire": 1,
            "start_pc": encode_pruned_pc(request.pc),
            "folded_history": self._history_values(previous.folded_history),
        }

    def submit_predict(
        self, pc: int, *, folded_history: int = 0, expected: Any = MISSING
    ) -> XTransfer[IttageLookup, IttagePrediction]:
        self._require_started()
        return self.prediction_scoreboard.submit(
            IttageLookup(pc, folded_history), expected=expected
        )

    async def drain_predictions(self):
        status = await self.prediction_scoreboard.drain(timeout_cycles=64)
        self.reference.raise_failure()
        return status

    async def predict(self, pc: int, *, folded_history: int = 0) -> IttagePrediction:
        actual = await self.submit_predict(pc, folded_history=folded_history)
        self.reference.raise_failure()
        return actual

    async def train(self, transaction: IttageTraining) -> None:
        self._require_started()
        branch_count = len(self.ports.training.bits.branches)
        if not 0 <= transaction.branch_index < branch_count:
            raise ValueError(f"ITTAGE branch_index must be in [0, {branch_count})")
        await self.train_batch(
            IttageBatchTraining(
                pc=transaction.pc,
                meta=transaction.meta,
                branches=(None,) * transaction.branch_index
                + (
                    IttageBranchFeedback(
                        position=transaction.position,
                        target=transaction.target,
                        taken=transaction.taken,
                        mispredict=transaction.mispredict,
                        branch_type=transaction.branch_type,
                        ras_action=transaction.ras_action,
                        valid=transaction.valid,
                    ),
                ),
                folded_history=transaction.folded_history,
            )
        )

    async def train_batch(self, transaction: IttageBatchTraining) -> None:
        await self.train_batches((transaction,))

    async def train_batches(
        self, transactions: Sequence[IttageBatchTraining], *,
        overlap_predictions: bool = False,
    ) -> XEvent:
        """Send adjacent feedback beats and retire their writes.

        Normally predictions drain before training. With overlap enabled,
        already-submitted predictions run alongside feedback; they all drain
        before lookup reads stop and the buffered updates retire. The returned
        event timestamps the end of the input burst, not write retirement.
        """

        self._require_started()
        if not transactions:
            raise ValueError("ITTAGE feedback burst must not be empty")
        # Validate the whole burst before changing any signals or submitting
        # its first beat; an invalid later beat must not partially train RTL.
        encoded = tuple(self._encode_batch_training(tx) for tx in transactions)
        if not overlap_predictions:
            await self.drain_predictions()
            self.lookup_driver.quiesce()
            self._last_a0_lookup = None
        event = await self.training_driver.send_many(encoded)
        if overlap_predictions:
            await self.drain_predictions()
            self.lookup_driver.quiesce()
            self._last_a0_lookup = None
        await self.training_activity.wait_idle()
        self.reference.raise_failure()
        return event

    def _encode_batch_training(self, transaction: IttageBatchTraining) -> dict[str, Any]:
        branch_count = len(self.ports.training.bits.branches)
        if not 1 <= len(transaction.branches) <= branch_count:
            raise ValueError(f"ITTAGE feedback requires 1 to {branch_count} branches")
        valid_branches = tuple(
            branch for branch in transaction.branches
            if branch is not None and branch.valid
        )
        if sum(bool(branch.mispredict) for branch in valid_branches) > 1:
            raise ValueError("ITTAGE feedback permits at most one mispredicted branch")
        if sum(
            bool(
                branch.taken
                and branch.branch_type == 3
                and (branch.ras_action & 1) == 0
            )
            for branch in valid_branches
        ) > 1:
            raise ValueError("ITTAGE feedback permits at most one qualifying branch")
        branches = transaction.branches + (None,) * (branch_count - len(transaction.branches))
        meta = dict(transaction.meta)
        # The prediction-side publication bit is not a training leaf in this
        # build; feeding a decoded prediction's metadata back is lossless
        # after dropping that monitor-only field.
        meta.pop('valid', None)
        for field in ("providerTarget_addr", "altProviderTarget_addr"):
            if field in meta:
                meta[field] = encode_pruned_pc(meta[field])
        return {
            "start_pc": encode_pruned_pc(transaction.pc),
            "folded_history": self._history_values(transaction.folded_history),
            "meta": meta,
            "branches": tuple(_encode_branch_feedback(branch) for branch in branches),
        }

    _decode = staticmethod(_decode)

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("ITTAGE agent requires an active Execution")
        self.reference.raise_failure()
