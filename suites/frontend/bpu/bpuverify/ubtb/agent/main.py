"""bpuverify.ubtb.agent.main components."""

from __future__ import annotations
from typing import Any
from toffee import Bundle
from toffee import ClockCycles
from toffee import Execution
from toffee import MISSING
from toffee import Scoreboard
from toffee import XTransfer
from bpuverify.common.checker.prediction import compare_prediction
from bpuverify.common.driver.signal import AsyncSingleCycleDriver
from bpuverify.common.driver.signal import ClockedWriteDriver
from bpuverify.common.driver.signal import ResetDriver
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.monitor.cycle import CycleMonitor
from bpuverify.ubtb.transaction.types import BranchTraining
from bpuverify.ubtb.transaction.types import PredictRequest
from bpuverify.ubtb.transaction.types import UbtbBatchTraining
from bpuverify.ubtb.bundle.ports import UbtbPorts
from bpuverify.ubtb.transaction.types import UbtbPrediction
from bpuverify.ubtb.monitor.decode import _decode_prediction_sample
from bpuverify.ubtb.driver.encoding import _encode_resolve
from bpuverify.ubtb.driver.encoding import _encode_training
from bpuverify.ubtb.driver.encoding import _encode_lookup
from bpuverify.ubtb.checker.semantic import UbtbSemanticChecker
from bpuverify.ubtb.monitor.semantic import UbtbSemanticMonitor


class UbtbAgent:
    """Own MicroBtb timing, pin ownership, driving, and structured sampling."""

    def __init__(self, dut: Any) -> None:
        self.dut = dut
        self.ports = UbtbPorts.bind(dut)
        self.reset_driver = ResetDriver(dut)
        self.control_driver = ClockedWriteDriver(self.ports.control)
        self.lookup_driver = AsyncSingleCycleDriver(
            self.ports.lookup,
            idle=lambda request: _encode_lookup(request, valid=0),
            encoder=lambda request: _encode_lookup(request, valid=1),
        )
        self.training_driver = AsyncSingleCycleDriver(
            PortBinding(
                dut.clock,
                Bundle(valid=self.ports.fast_train.valid, bits=self.ports.fast_train.bits),
                self.ports.fast_train.name,
            ),
            idle=lambda request: self._encode_training(request, valid=0),
            encoder=lambda request: self._encode_training(request, valid=1),
        )
        self.resolve_driver = AsyncSingleCycleDriver(
            PortBinding(
                dut.clock,
                Bundle(valid=self.ports.training.valid, bits=self.ports.training.bits),
                self.ports.training.name,
            ),
            idle=lambda request: self._encode_resolve(request, valid=0),
            encoder=lambda request: self._encode_resolve(request, valid=1),
        )
        self.prediction_monitor = CycleMonitor(
            self.ports.prediction, decoder=self._decode_prediction_sample
        )
        self.reference = UbtbSemanticChecker()
        self.reference_monitor = UbtbSemanticMonitor(dut, self.ports)
        self.prediction_scoreboard = Scoreboard(
            "ubtb.prediction",
            compare=compare_prediction,
            expected=self.reference.response_expected,
        )
        self._execution: Execution | None = None
        self._started = False

    async def start(self, execution: Execution) -> "UbtbAgent":
        if self._started:
            raise RuntimeError("MicroBtb agent is already started")
        self._execution = execution
        await self.reset_driver.__aenter__()
        try:
            await self.control_driver.__aenter__()
            self.reference_monitor.start(execution, self.reference)
            self.lookup_driver.start(execution)
            self.prediction_scoreboard.bind(
                execution,
                driver=self.lookup_driver,
                monitor=self.prediction_monitor,
                clock=self.dut.clock,
                response_timeout_cycles=64,
                latency_cycles=1,
                sampled=True,
            )
            self.training_driver.start(execution)
            self.resolve_driver.start(execution)
            await self.control_driver.send({"enable": 1})
        except BaseException:
            await self.reference_monitor.aclose()
            await self.resolve_driver.aclose()
            await self.training_driver.aclose()
            await self.lookup_driver.aclose()
            self.control_driver.close()
            self.reset_driver.close()
            raise
        self._started = True
        return self

    async def aclose(self) -> None:
        try:
            await self.prediction_scoreboard.aclose()
        finally:
            await self.reference_monitor.aclose()
            await self.resolve_driver.aclose()
            await self.training_driver.aclose()
            await self.lookup_driver.aclose()
            self.control_driver.close()
            self.reset_driver.close()
            self._execution = None
            self._started = False
        self.reference.raise_unobserved_failure()

    async def reset(self, cycles: int = 3) -> None:
        self._require_started()
        await self.reset_driver.send(cycles)
        await self.set_enabled(True)
        status = self.ports.status.bits.sample()
        if not status.reset_done.as_int() or not status.train_ready.as_int():
            raise AssertionError(
                "MicroBtb did not become ready after reset: "
                f"reset_done={status.reset_done}, train_ready={status.train_ready}"
            )
        self.reference.raise_failure()

    async def set_enabled(self, enabled: bool) -> None:
        """Control lookup and fastTrain gates independently of requests."""

        self._require_started()
        self.lookup_driver.quiesce()
        await self.control_driver.send({"enable": int(enabled)})
        self.reference.raise_failure()

    async def predict(self, pc: int) -> UbtbPrediction:
        prediction = await self.submit_predict(pc)
        self.reference.raise_failure()
        return prediction

    def submit_predict(
        self,
        pc: int,
        *,
        expected: Any = MISSING,
    ) -> XTransfer[PredictRequest, UbtbPrediction]:
        self._require_started()
        self.reference.raise_failure()
        return self.prediction_scoreboard.submit(
            PredictRequest(pc), expected=expected
        )

    async def drain_predictions(self):
        status = await self.prediction_scoreboard.drain(timeout_cycles=64)
        self.reference.raise_failure()
        return status

    _decode_prediction_sample = staticmethod(_decode_prediction_sample)

    async def train(self, transaction: BranchTraining) -> None:
        self._require_started()
        await self.training_driver.send(transaction)
        # RiseWrite commits on the next rising phase; the DUT samples this
        # request one clock later. Keep that launch detail inside the agent.
        await ClockCycles(self.dut.clock, 1)
        self.reference.raise_failure()

    async def train_resolve(
        self,
        transaction: UbtbBatchTraining,
        *,
        fast_train: BranchTraining | None = None,
    ):
        """Submit resolve, optionally overlapping fastTrain on the same beat.

        Both drivers launch before either is awaited. The overlap is checked
        here, so scenarios cannot accidentally test sequential arbitration.
        """

        self._require_started()
        # Validate before either source can produce a partial concurrent beat.
        self._encode_resolve(transaction, valid=1)
        if fast_train is not None:
            self._encode_training(fast_train, valid=1)
        resolve = self.resolve_driver.send(transaction)
        fast = None if fast_train is None else self.training_driver.send(fast_train)
        resolve_event = await resolve
        if fast is not None:
            fast_event = await fast
            if fast_event.tick != resolve_event.tick:
                raise AssertionError(
                    "MicroBTB training sources did not overlap: "
                    f"resolve={resolve_event.tick}, fast={fast_event.tick}"
                )
        await ClockCycles(self.dut.clock, 1)
        self.reference.raise_failure()
        return resolve_event

    async def predict_on_training_write(
        self, transaction: BranchTraining, pc: int
    ) -> UbtbPrediction:
        """Look up a PC while the preceding accepted train writes its entry."""

        self._require_started()
        train_event = await self.training_driver.send(transaction)
        transfer = self.submit_predict(pc)
        prediction = await transfer
        assert transfer.accepted_event is not None
        if transfer.accepted_event.tick != train_event.tick + 2:
            raise AssertionError(
                "MicroBTB lookup missed the training write cycle: "
                f"train={train_event.tick}, lookup={transfer.accepted_event.tick}"
            )
        self.reference.raise_failure()
        return prediction

    async def train_contiguous(self, transactions: tuple[BranchTraining, ...]):
        """Submit adjacent valid training cycles without an inter-request bubble."""

        self._require_started()
        if not transactions:
            raise ValueError("contiguous training requires at least one transaction")
        for transaction in transactions:
            self._encode_training(transaction, valid=1)
        transfers = tuple(self.training_driver.send(transaction) for transaction in transactions)
        await transfers[-1]
        await ClockCycles(self.dut.clock, 1)
        self.reference.raise_failure()
        return transfers

    _encode_training = staticmethod(_encode_training)

    _encode_resolve = staticmethod(_encode_resolve)

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("MicroBtb agent requires an active Execution")
        self.reference.raise_failure()
