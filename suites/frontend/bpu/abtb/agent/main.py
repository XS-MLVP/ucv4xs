"""suites.frontend.bpu.abtb.agent.main components."""

from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Any
from toffee import ClockCycles
from suites.frontend.bpu.monitors.activity import ActivityMonitor
from suites.frontend.bpu.abtb.bundle.activity import training_activity
from suites.frontend.bpu.runtime.wait import wait_reset_done
from toffee import Execution
from toffee import MISSING
from toffee import Scoreboard
from toffee import XTransfer
from suites.frontend.bpu.checkers.prediction import compare_prediction
from suites.frontend.bpu.abtb.checker.semantic import AbtbSemanticChecker
from suites.frontend.bpu.abtb.monitor.semantic import AbtbSemanticMonitor
from suites.frontend.bpu.drivers.signal import AsyncSingleCycleDriver
from suites.frontend.bpu.drivers.signal import ClockedWriteDriver
from suites.frontend.bpu.drivers.signal import PulseDriver
from suites.frontend.bpu.drivers.signal import ResetDriver
from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.abtb.transaction.types import AbtbLookup
from suites.frontend.bpu.abtb.bundle.ports import AbtbPorts
from suites.frontend.bpu.abtb.transaction.types import AbtbPrediction
from suites.frontend.bpu.abtb.transaction.types import AbtbTraining
from suites.frontend.bpu.abtb.monitor.decode import _decode
from suites.frontend.bpu.abtb.driver.encoding import _encode_training


class AbtbAgent:
    def __init__(self, dut: Any) -> None:
        self.dut = dut
        self.ports = AbtbPorts.bind(dut)
        self.training_activity = ActivityMonitor(training_activity(dut))
        self._last_s0_lookup: AbtbLookup | None = None
        self.reset_driver = ResetDriver(dut)
        self.control_driver = ClockedWriteDriver(self.ports.control)
        self.lookup_driver = AsyncSingleCycleDriver(
            self.ports.lookup,
            idle=lambda request: {
                "s0_fire": 0 if request is None else 1,
                "s1_fire": 1,
                "s2_fire": 1,
                "start_pc": 0 if request is None else request.pc,
                "new_start_pc": 0 if request is None else request.pc,
                "path_hash": 0 if request is None else request.path_hash,
                "s2_override": 0,
                "s3_override": 0,
                "override_start_pc": 0 if request is None else request.pc,
                "redirect": 0,
            },
            encoder=self._encode_lookup,
        )
        self.training_driver = PulseDriver(self.ports.training)
        self.prediction_monitor = CycleMonitor(
            self.ports.prediction, decoder=self._decode
        )
        self.reference = AbtbSemanticChecker()
        self.reference_monitor = AbtbSemanticMonitor(dut, self.ports)
        self.prediction_scoreboard = Scoreboard(
            "abtb.prediction",
            compare=compare_prediction,
            expected=self.reference.response_expected,
        )
        self._execution: Execution | None = None
        self._started = False
        self._training_override = None

    async def start(self, execution: Execution) -> "AbtbAgent":
        if self._started:
            raise RuntimeError("AheadBTB agent is already started")
        self._execution = execution
        self.reference_monitor.start(execution, self.reference)
        await self.reset_driver.__aenter__()
        try:
            await self.control_driver.__aenter__()
            self.lookup_driver.start(execution)
            self.prediction_scoreboard.bind(
                execution,
                driver=self.lookup_driver,
                monitor=self.prediction_monitor,
                clock=self.dut.clock,
                response_timeout_cycles=64,
                latency_cycles=2,
                sampled=True,
            )
            await self.training_driver.__aenter__()
            await self.control_driver.send({"enable": 1})
        except BaseException:
            await self.reference_monitor.aclose()
            await self.lookup_driver.aclose()
            self.training_driver.close()
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
            self.training_driver.close()
            await self.lookup_driver.aclose()
            self.control_driver.close()
            self.reset_driver.close()
            self._execution = None
            self._started = False
        self.reference.raise_unobserved_failure()

    async def reset(self, cycles: int = 3) -> int:
        self._require_started()
        self.lookup_driver.quiesce()
        self._last_s0_lookup = None
        await self.reset_driver.send(cycles)
        await self.set_enabled(True)
        waited = (await wait_reset_done(self.ports.status)).samples
        if not self.ports.status.bits.sample().train_ready.as_int():
            raise AssertionError("AheadBTB training port is not ready")
        return waited

    @property
    def execution(self) -> Execution:
        """Active execution for agent-owned passive observations."""

        self._require_started()
        assert self._execution is not None
        return self._execution

    @asynccontextmanager
    async def using_training_driver(self, driver):
        """Temporarily replace the sole writer; restore it even after failure.

        Replacement drivers consume the same encoded payload as PulseDriver.
        Their own async context owns pending transfers and signal capabilities.
        Nested replacements are rejected rather than silently stealing ownership.
        """

        self._require_started()
        if self._training_override is not None:
            raise RuntimeError("AheadBTB training driver is already replaced")
        if driver is self.training_driver or driver.binding is not self.ports.training:
            raise ValueError("replacement must be a new driver for this training port")
        original = self.training_driver
        original.close()
        self._training_override = driver
        try:
            async with driver:
                self.training_driver = driver
                yield driver
        finally:
            self.training_driver = original
            self._training_override = None
            await original.__aenter__()

    @staticmethod
    def encode_training(transaction: AbtbTraining) -> dict[str, Any]:
        """Canonical payload shared by ordinary and asynchronous training."""

        return AbtbAgent._encode_training(transaction)

    async def set_enabled(self, enabled: bool) -> None:
        """Control prediction and fastTrain gates independently of lookups."""

        self._require_started()
        self.lookup_driver.quiesce()
        self._last_s0_lookup = None
        await self.control_driver.send({"enable": int(enabled)})

    def _encode_lookup(self, request: AbtbLookup) -> dict[str, Any]:
        # S0 selects the bank/set now; S1 compares the preceding request's PC
        # with the returned SRAM entries on this same cycle.
        previous = self._last_s0_lookup or request
        self._last_s0_lookup = request
        return {
            "s0_fire": 1,
            "s1_fire": 1,
            "s2_fire": 1,
            "start_pc": request.pc,
            "new_start_pc": previous.pc,
            "path_hash": request.path_hash,
            "s2_override": int(request.override == "s2"),
            "s3_override": int(request.override == "s3"),
            "override_start_pc": request.pc if request.override_pc is None else request.override_pc,
            "redirect": int(request.redirect),
        }

    def submit_predict(
        self,
        pc: int,
        *,
        path_hash: int = 0,
        override: str | None = None,
        override_pc: int | None = None,
        redirect: bool = False,
        expected: Any = MISSING,
    ) -> XTransfer[AbtbLookup, AbtbPrediction]:
        self._require_started()
        if not 0 <= path_hash < 16:
            raise ValueError("AheadBTB path_hash must fit the four index-hash bits")
        if override not in (None, "s2", "s3"):
            raise ValueError(f"unknown AheadBTB override stage: {override!r}")
        if type(redirect) is not bool:
            raise ValueError("AheadBTB redirect must be an explicit bool")
        return self.prediction_scoreboard.submit(
            AbtbLookup(pc, path_hash, override, override_pc, redirect), expected=expected
        )

    async def drain_predictions(self):
        result = await self.prediction_scoreboard.drain(timeout_cycles=64)
        self.reference.raise_failure()
        return result

    async def drain_bank_writes(self) -> None:
        """Give buffered writes a read-free window in the single-port banks.

        Lookup-idle normally keeps S0 reads active to preserve the pipeline;
        bank reads take priority over writes. Four write-buffer slots plus the
        read pipeline fit within this eight-cycle quiet window.
        """

        self._require_started()
        await self.drain_predictions()
        self.lookup_driver.quiesce()
        self._last_s0_lookup = None
        await self.training_activity.wait_idle()
        self.reference.raise_failure()

    async def predict(self, pc: int, *, path_hash: int = 0) -> AbtbPrediction:
        return await self.submit_predict(pc, path_hash=path_hash)

    async def recover_prediction(
        self,
        pc: int,
        *,
        stage: str,
        override_pc: int,
        path_hash: int = 0,
    ) -> AbtbPrediction:
        """Observe S2/S3 replay one cycle after its override input is accepted."""

        transfer = self.submit_predict(
            pc,
            path_hash=path_hash,
            override=stage,
            override_pc=override_pc,
        )
        await transfer.wait_processing()
        event = await ClockCycles(self.dut.clock, 1)
        observed = self.prediction_monitor.sample_at(event).value
        await transfer
        self.reference.raise_failure()
        return observed

    async def train(self, transaction: AbtbTraining) -> None:
        self._require_started()
        # The last lookup leaves s0_fire asserted. Stop continued reads before
        # fastTrain; this predictor did not allocate while those reads ran.
        self.lookup_driver.quiesce()
        self._last_s0_lookup = None
        await self._pulse_training(transaction)
        await self.training_activity.wait_idle()
        self.reference.raise_failure()

    async def train_under_read_pressure(self, transaction: AbtbTraining) -> None:
        """Pulse fastTrain without stopping outstanding or idle lookup reads.

        A single-port bank may buffer the write until ``drain_bank_writes``
        provides a read-free window. This is intentionally not a settled
        training operation like ``train``.
        """

        self._require_started()
        await self._pulse_training(transaction)
        self.reference.raise_failure()

    async def _pulse_training(self, transaction: AbtbTraining) -> None:
        await self.training_driver.send(self._encode_training(transaction))

    _encode_training = staticmethod(_encode_training)

    _decode = staticmethod(_decode)

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("AheadBTB agent requires an active Execution")
