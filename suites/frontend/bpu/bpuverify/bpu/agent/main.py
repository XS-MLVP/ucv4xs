"""bpuverify.bpu.agent.main components."""

from __future__ import annotations
import asyncio
import contextlib
from typing import Any
from toffee import ClockCycles
from toffee import Execution
from toffee import ReadyValidMonitor
from toffee import Bundle
from toffee.signals import sample_signal
from bpuverify.common.monitor.activity import ActivityMonitor
from bpuverify.bpu.bundle.activity import training_activity
from bpuverify.bpu.bundle.activity import control_activity, initialization_activity
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.monitor.cycle import CycleMonitor
from bpuverify.common.monitor.activity import TRAINING_TIMEOUT_CYCLES
from bpuverify.common.env.wait import wait_condition, RESET_TIMEOUT_CYCLES
from bpuverify.bpu.driver.training import BpuTrainingDriver
from bpuverify.bpu.driver.control import BpuControlDriver, PredictionWindow
from bpuverify.common.transaction.cycle import CycleTransaction
from bpuverify.common.driver.signal import PulseDriver
from bpuverify.common.driver.signal import ResetDriver
from bpuverify.bpu.transaction.types import BpuBackpressure
from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBurstActivity
from bpuverify.bpu.transaction.types import BpuConcurrentActivity
from bpuverify.bpu.transaction.types import BpuMeta
from bpuverify.bpu.bundle.ports import BpuPorts
from bpuverify.bpu.transaction.types import BpuPrediction
from bpuverify.bpu.transaction.types import BpuPredictionSample
from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.transaction.types import BpuStalledRedirect
from bpuverify.bpu.transaction.types import BpuTraining
from bpuverify.bpu.transaction.types import BpuTransaction
from bpuverify.bpu.monitor.decode import _decode_meta
from bpuverify.bpu.monitor.decode import _decode_prediction
from bpuverify.bpu.driver.encoding import _encode_training
from bpuverify.bpu.driver.encoding import _single_training


class BpuAgent:
    """Own all integrated-BPU pins and expose transaction-level operations."""

    def __init__(self, dut: Any) -> None:
        self.dut = dut
        self.ports = BpuPorts.bind(dut)
        self.training_activity = ActivityMonitor(training_activity(dut))
        self.applied_control = ActivityMonitor(control_activity(dut))
        self.initialization = ActivityMonitor(initialization_activity(dut))
        self.retirement_monitor = CycleMonitor(PortBinding(dut.clock,
            Bundle(valid=self.ports.meta.valid, pc=self.ports.meta.bits.perf.start_pc),
            'bpu.pipeline_retirement'), decoder=lambda s: dict(valid=s.valid.as_int(), pc=s.pc.as_int()))
        self.reset_driver = ResetDriver(dut)
        self.control_driver = BpuControlDriver(self.ports.control)
        self.training_driver = BpuTrainingDriver(
            self.ports.training, encoder=self._encode_training
        )
        self.redirect_driver = PulseDriver(self.ports.redirect)
        self._make_stream_monitors()
        self._phr_observation = None
        self._execution: Execution | None = None
        self._reset_vector = 0
        self._predictor_enabled = {
            name: 1 for name in ("ubtb", "abtb", "mbtb", "tage", "sc", "ittage", "ras")
        }
        self._prediction_ready = 1
        self._meta_ready = 1
        self._transaction_aligned = False
        self._started = False

    def _make_stream_monitors(self) -> None:
        """Closed toffee monitors are terminal: renew, never clear queues."""

        self.prediction_monitor = ReadyValidMonitor(
            self.ports.prediction,
            decoder=self._decode_prediction,
            capacity=1024,
        )
        self.meta_monitor = ReadyValidMonitor(
            self.ports.meta, decoder=self._decode_meta, capacity=1024
        )

    def observe_phr(self, checker):
        """Own coherent PHR/pipeline observation until context exit.

        Enter before reset. During this scope ``next_transaction`` uses actual
        stage fire/flush association, and ``redirect`` returns the observed
        acceptance tick. Independent raw-stream consumers cannot run alongside
        it. The ordinary monitors are renewed when the scope ends.
        """

        from bpuverify.bpu.env.phr.observation import BpuPhrObservation

        return BpuPhrObservation(self, checker)

    async def start(self, execution: Execution) -> "BpuAgent":
        if self._started:
            raise RuntimeError("BPU agent is already started")
        self._execution = execution
        await self.reset_driver.__aenter__()
        await self.control_driver.__aenter__()
        await self.training_driver.__aenter__()
        await self.redirect_driver.__aenter__()
        self.prediction_monitor.start(execution)
        self.meta_monitor.start(execution)
        self._started = True
        return self

    async def aclose(self) -> None:
        if self._phr_observation is not None:
            await self._phr_observation.aclose(resume_streams=False)
        await self.prediction_monitor.aclose()
        await self.meta_monitor.aclose()
        self.redirect_driver.close()
        await self.training_driver.aclose()
        self.control_driver.close()
        self.reset_driver.close()
        self._execution = None
        self._started = False

    async def reset(self, reset_vector: int, cycles: int = 3) -> None:
        self._require_started()
        self._reset_vector = reset_vector
        self._transaction_aligned = False
        await self._drive_control()
        await self.reset_driver.send(cycles)
        # DefaultConfig SRAM clearing can consume 512 cycles. Observe the
        # aggregate hardware-ready condition before starting a prediction
        # deadline; monitors keep checking every reset/initialization cycle.
        await wait_condition(self.dut.clock,
            sample=lambda: self.initialization._capture(None)['sram_ready'],
            satisfied=lambda state: state == {'sramResetDone': 1},
            name='bpu.sram_initialization_complete', timeout_cycles=RESET_TIMEOUT_CYCLES)

    async def set_enabled(self, enabled: bool) -> None:
        self._require_started()
        for name in self._predictor_enabled:
            self._predictor_enabled[name] = int(enabled)
        await self._drive_control()

    async def configure_predictors(
        self, *, settle: bool = False, **enabled: bool
    ) -> None:
        """Set selected predictor enables without exposing control pins to tests."""

        self._require_started()
        unknown = set(enabled) - self._predictor_enabled.keys()
        if unknown:
            raise ValueError(f"unknown BPU predictor(s): {sorted(unknown)}")
        for name, value in enabled.items():
            self._predictor_enabled[name] = int(value)
        await self._drive_control()
        if settle:
            expected = {f'csrCtrl_delay.REG_1_{key}Enable': value
                        for key, value in self._predictor_enabled.items()}
            await wait_condition(self.dut.clock,
                sample=lambda: self.applied_control._capture(None)['enable'],
                satisfied=lambda state: state == expected, name='bpu.predictor_controls_applied',
                timeout_cycles=TRAINING_TIMEOUT_CYCLES)

    async def set_ready(
        self,
        *,
        prediction: bool,
        meta: bool,
    ) -> int:
        """Control FTQ backpressure and return its committed boundary tick."""

        self._require_started()
        self._prediction_ready = int(prediction)
        self._meta_ready = int(meta)
        return (await self._drive_control()).tick

    def sample_stalled_prediction(self) -> BpuPredictionSample:
        """Sample the current S1 transfer without accepting it."""

        self._require_started()
        if self._prediction_ready:
            raise RuntimeError("prediction must be backpressured before sampling")
        return BpuPredictionSample(
            sample_signal(self.ports.prediction.valid).as_int(),
            self._decode_prediction(self.ports.prediction.bits.sample()),
        )

    async def refresh_stalled_prediction(self) -> BpuPredictionSample:
        """Let enabled predictors read a fresh request, then hold its S1 result.

        Keep the ready-high interval short so S3 fastTrain cannot converge a
        deliberately distinct early-source target during arbitration probes.
        """

        self._require_started()
        if self._prediction_ready:
            raise RuntimeError("prediction must already be backpressured")
        # Commit each level with the control driver's minimum launch. An
        # extra ready-high waiting cycle accepts an extra FTQ token, which
        # makes a single refresh unsuitable for bounded pipeline stepping.
        self._prediction_ready = 1
        self._meta_ready = 1
        try:
            await self._drive_control(cycles=0)
        finally:
            self._prediction_ready = 0
            await self._drive_control(cycles=0)
        return self.sample_stalled_prediction()

    async def hold_backpressure(self, cycles: int = 4) -> BpuBackpressure:
        """Stall prediction and return snapshots of its held transfer.

        The integrated BPU honors ``prediction.ready``.  Its metadata port is
        valid-only in the RTL implementation even though the generated IO has
        a ready leaf, so this operation deliberately keeps metadata ready.
        """

        if cycles <= 0:
            raise ValueError("backpressure cycles must be positive")
        await self.next_prediction(start_pc=self._reset_vector)
        await self.set_ready(prediction=False, meta=True)
        try:
            before = await self._wait_stalled_prediction()
            await ClockCycles(self.dut.clock, cycles)  # Requested stall duration.
            after = self.sample_stalled_prediction()
        finally:
            await self.set_ready(prediction=True, meta=True)
        return BpuBackpressure(
            (before.valid, after.valid),
            (before.prediction, after.prediction),
        )

    async def _wait_stalled_prediction(self, *, timeout_cycles=TRAINING_TIMEOUT_CYCLES):
        result = await wait_condition(self.dut.clock,
            sample=self.sample_stalled_prediction, satisfied=lambda state: bool(state.valid),
            name='bpu.stalled_prediction_valid', timeout_cycles=timeout_cycles)
        return result.state

    async def pause_prediction_reads(self, cycles: int | None = None) -> None:
        """Let read-priority early-predictor banks commit pending fastTrain writes."""

        self._require_started()
        if cycles is not None and cycles <= 0:
            raise ValueError("pause cycles must be positive")
        await self.set_ready(prediction=False, meta=True)
        try:
            if cycles is None:
                # MicroTAGE SRAMs continuously select a bank, even with no
                # request valid (MicroTageTable.scala). Do not falsely promise
                # to empty its shadow buffer merely by lowering FTQ ready.
                await self.drain_prediction_work()
            else:
                await ClockCycles(self.dut.clock, cycles)  # Explicit scenario hold.
        finally:
            await self.set_ready(prediction=True, meta=True)

    async def drain_prediction_work(self):
        """Drain accepted FTQ/fastTrain work while younger predictions are held.

        This does not promise to clear MicroTAGE's continuously selected SRAM
        shadow. It never changes ready/enable or waits an empirical delay.
        """
        self._require_started()
        if self._prediction_ready:
            raise RuntimeError('prediction work drain requires prediction backpressure')
        return await self.training_activity.wait_idle(
            'reads', 'pipeline', 'writes', 'fast_pipeline', 'fast_writes')

    async def redirect_while_backpressured(
        self, transaction: BpuRedirect, *, limit: int = 64
    ) -> BpuStalledRedirect:
        """Observe a redirect replacing a stalled prediction, then its first accept.

        The monitor may already contain older accepted predictions. Its event
        timestamps distinguish those from the first transfer after ready resumes.
        """

        self._require_stream_observation()
        if limit <= 0:
            raise ValueError("prediction limit must be positive")
        await self.set_ready(prediction=False, meta=True)
        try:
            sample = await self._wait_stalled_prediction(timeout_cycles=limit)
            stalled_valid, stalled = sample.valid, sample.prediction
            await self.redirect(transaction)
            boundary = await ClockCycles(self.dut.clock, 1)
            redirected_valid = sample_signal(self.ports.prediction.valid).as_int()
            redirected = self._decode_prediction(self.ports.prediction.bits.sample())
        finally:
            await self.set_ready(prediction=True, meta=True)

        for _ in range(limit):
            accepted = await self.prediction_monitor.recv()
            if accepted.accepted_tick > boundary.tick:
                return BpuStalledRedirect(
                    stalled_valid,
                    stalled,
                    redirected_valid,
                    redirected,
                    accepted.accepted_tick,
                    accepted.value,
                )
        raise AssertionError(
            "BPU did not accept a prediction after stalled redirect; "
            f"target={transaction.pc:#x}, boundary_tick={boundary.tick}, "
            f"stalled={stalled!r}, redirected={redirected!r}"
        )

    async def next_prediction(
        self,
        *,
        start_pc: int | None = None,
        require_taken: bool = False,
        stage: str | None = None,
        target: int | None = None,
        after_tick: int | None = None,
        limit: int = 512,
    ) -> tuple[int, BpuPrediction]:
        self._require_stream_observation()
        if stage not in (None, "s1", "s2", "s3"):
            raise ValueError("stage must be one of: s1, s2, s3")
        observed: list[tuple[int, int, int, int]] = []
        for index in range(limit + 1):
            transfer = await self.prediction_monitor.recv()
            prediction = transfer.value
            observed.append((
                prediction.start_pc,
                prediction.target,
                prediction.s2_override,
                prediction.s3_override,
            ))
            if (after_tick is None or transfer.accepted_tick > after_tick) and (
                start_pc is None or prediction.start_pc == start_pc
            ) and (
                not require_taken or prediction.taken
            ) and (
                target is None or prediction.target == target
            ) and (
                stage is None
                or (stage == "s1" and not prediction.s2_override and not prediction.s3_override)
                or (stage == "s2" and prediction.s2_override)
                or (stage == "s3" and prediction.s3_override)
            ):
                return index, prediction
        raise AssertionError(
            f"BPU prediction did not arrive for start_pc={start_pc!r}, "
            f"target={target!r}, stage={stage!r}, after_tick={after_tick!r}; "
            f"observed={observed[:12]}"
        )

    async def next_meta(self) -> BpuMeta:
        self._require_stream_observation()
        return (await self.meta_monitor.recv()).value

    async def next_transaction(
        self,
        *,
        start_pc: int | None = None,
        require_taken: bool = False,
        after_tick: int | None = None,
        limit: int = 512,
    ) -> BpuTransaction:
        """Return an S1 prediction and its causally associated S3 metadata."""

        self._require_started()
        effective_start_pc = start_pc
        if not self._transaction_aligned and effective_start_pc is None:
            effective_start_pc = self._reset_vector
        if self._phr_observation is not None:
            result = await self._phr_observation.next_transaction(
                start_pc=effective_start_pc, require_taken=require_taken,
                after_tick=after_tick, limit=limit,
            )
            self._transaction_aligned = True
            return result
        observed = []
        for _ in range(limit + 1):
            prediction_transfer = await self.prediction_monitor.recv()
            prediction = prediction_transfer.value
            observed.append(prediction.start_pc)
            if after_tick is not None and prediction_transfer.accepted_tick <= after_tick:
                continue
            if prediction.s2_override or prediction.s3_override:
                continue
            if (
                effective_start_pc is not None
                and prediction.start_pc != effective_start_pc
            ):
                continue
            if require_taken and not prediction.taken:
                continue

            expected_meta_tick = prediction_transfer.accepted_tick + 4
            while True:
                meta_transfer = await self.meta_monitor.recv()
                if meta_transfer.accepted_tick < expected_meta_tick:
                    continue
                if meta_transfer.accepted_tick != expected_meta_tick:
                    raise AssertionError(
                        "BPU prediction/meta latency mismatch: "
                        f"prediction_tick={prediction_transfer.accepted_tick}, "
                        f"meta_tick={meta_transfer.accepted_tick}"
                    )
                perf = meta_transfer.value.perf
                if (
                    perf.start_pc != prediction.start_pc
                    or perf.s1_target != prediction.target
                    or perf.s1_taken != prediction.taken
                    or perf.s1_position != prediction.position
                ):
                    raise AssertionError(
                        "BPU prediction/perf echo mismatch: "
                        f"prediction_tick={prediction_transfer.accepted_tick}, "
                        f"meta_tick={meta_transfer.accepted_tick}, "
                        f"prediction={prediction!r}, perf={perf!r}"
                    )
                self._transaction_aligned = True
                return BpuTransaction(
                    prediction_tick=prediction_transfer.accepted_tick,
                    meta_tick=meta_transfer.accepted_tick,
                    prediction=prediction,
                    meta=meta_transfer.value,
                )
        raise AssertionError(
            f"BPU transaction did not arrive for {effective_start_pc!r} "
            f"after_tick={after_tick!r}; "
            f"observed={observed[:12]}"
        )

    async def next_s3_correction(
        self,
        *,
        start_pc: int | None = None,
        target: int | None = None,
        after_tick: int | None = None,
        limit: int = 512,
    ) -> BpuTransaction:
        """Pair an accepted S3 override with its same-cycle source echo."""

        self._require_stream_observation()
        observed: list[tuple[int, int, int]] = []
        for _ in range(limit + 1):
            prediction_transfer = await self.prediction_monitor.recv()
            prediction = prediction_transfer.value
            observed.append((
                prediction_transfer.accepted_tick,
                prediction.start_pc,
                prediction.s3_override,
            ))
            if (
                not prediction.s3_override
                or after_tick is not None and prediction_transfer.accepted_tick <= after_tick
                or start_pc is not None and prediction.start_pc != start_pc
                or target is not None and prediction.target != target
            ):
                continue

            while True:
                meta_transfer = await self.meta_monitor.recv()
                if meta_transfer.accepted_tick < prediction_transfer.accepted_tick:
                    continue
                if meta_transfer.accepted_tick != prediction_transfer.accepted_tick:
                    raise AssertionError(
                        "BPU S3 correction/meta timing mismatch: "
                        f"prediction_tick={prediction_transfer.accepted_tick}, "
                        f"meta_tick={meta_transfer.accepted_tick}, "
                        f"prediction={prediction!r}"
                    )
                if meta_transfer.value.perf.start_pc != prediction.start_pc:
                    raise AssertionError(
                        "BPU S3 correction/meta PC mismatch: "
                        f"prediction={prediction!r}, "
                        f"perf={meta_transfer.value.perf!r}"
                    )
                return BpuTransaction(
                    prediction_tick=prediction_transfer.accepted_tick,
                    meta_tick=meta_transfer.accepted_tick,
                    prediction=prediction,
                    meta=meta_transfer.value,
                )
        raise AssertionError(
            "BPU S3 correction did not arrive: "
            f"start_pc={start_pc!r}, target={target!r}, "
            f"after_tick={after_tick!r}, observed={observed[:12]}"
        )

    async def corrections_for(self, transaction: BpuTransaction, *, limit: int = 64):
        """Collect every override in this request's causal S1-to-S3 window.

        Keep ticks and wrong-PC/extra overrides: the checker must reject them,
        rather than hiding them behind an expected-target/PC search filter.
        A following monitored transfer closes the window; monitor ordering is
        retained and later same-PC requests cannot be associated backwards.
        """
        self._require_stream_observation()
        if type(limit) is not int or limit <= 0:
            raise ValueError('BPU correction window limit must be positive')
        repairs = []
        for _ in range(limit):
            transfer = await self.prediction_monitor.recv()
            if transfer.accepted_tick <= transaction.prediction_tick:
                continue
            if transfer.accepted_tick > transaction.meta_tick:
                return tuple(repairs)
            prediction = transfer.value
            if prediction.s2_override or prediction.s3_override:
                repairs.append((transfer.accepted_tick,prediction))
        raise AssertionError('BPU correction observation did not close its causal S3 window')

    async def correction_for(
        self,
        transaction: BpuTransaction,
        *,
        target: int,
        limit: int = 64,
    ) -> BpuPrediction | None:
        """Find this S1 transaction's full-target S2/S3 override, if any.

        Accepted transfer ticks bound the search from the S1 prediction to
        the same request's S3 metadata. A later request to the same PC cannot
        masquerade as a repair of this transaction.
        """

        self._require_stream_observation()
        for _ in range(limit + 1):
            transfer = await self.prediction_monitor.recv()
            if transfer.accepted_tick <= transaction.prediction_tick:
                continue
            if transfer.accepted_tick > transaction.meta_tick:
                return None
            prediction = transfer.value
            if (
                prediction.start_pc == transaction.prediction.start_pc
                and prediction.target == target
                and (prediction.s2_override or prediction.s3_override)
            ):
                return prediction
        raise AssertionError(
            "BPU correction search exceeded transfer limit before metadata: "
            f"prediction_tick={transaction.prediction_tick}, "
            f"meta_tick={transaction.meta_tick}, limit={limit}"
        )

    async def train(self, transaction: BpuTraining, *, prediction_pause: bool = False) -> None:
        """Confirm feedback commit, optionally establishing a read-free window.

        Keep active-stream behavior unless a scenario requests read-free
        commit. Same-bank continuous reads need prediction_pause=True.
        """
        await self.train_batch(self._single_training(transaction), prediction_pause=prediction_pause)

    async def train_batch(self, transaction: BpuBatchTraining, *, prediction_pause: bool = False) -> None:
        """Feedback followed by commit; pin timing stays inside the agent."""
        self._require_started()
        if prediction_pause:
            await self.train_batch_with_prediction_pause(transaction)
        else:
            await self.training_driver.send(transaction)
            await self.wait_training(committed=True)

    async def train_batches(
        self, transactions: tuple[BpuBatchTraining, ...]
    ) -> tuple[int, ...]:
        """Submit consecutive FTQ beats and wait for their pipeline effects.

        The async driver queues every beat before acceptance is awaited. This
        variant leaves prediction traffic active; the paused variant below is
        for single-port tagged predictor SRAM reads.
        """

        self._require_started()
        if not transactions:
            raise ValueError("BPU feedback burst must not be empty")
        handles = tuple(self.training_driver.send(tx) for tx in transactions)
        accepted_ticks = tuple([(await handle).tick for handle in handles])
        await self.wait_training()
        return accepted_ticks

    async def train_batches_during_stream(
        self,
        transactions: tuple[BpuBatchTraining, ...],
        *,
        prediction_limit: int = 1024,
    ) -> BpuBurstActivity:
        """Return monitored prediction accepts concurrent with a train burst."""

        self._require_stream_observation()
        if not self._prediction_ready:
            raise RuntimeError("prediction stream must be accepting")
        if prediction_limit <= 0:
            raise ValueError("prediction limit must be positive")
        training_ticks = await self.train_batches(transactions)
        # This helper checks the subsequent provider state. Its intended
        # bank-disjoint stream permits actual SRAM commit without pausing.
        await self.wait_training(committed=True)
        observed = []
        for _ in range(prediction_limit):
            item = await self.prediction_monitor.recv()
            if item.accepted_tick > training_ticks[-1]:
                break
            if item.accepted_tick >= training_ticks[0]:
                observed.append(item)
        else:
            raise AssertionError(
                "BPU prediction monitor did not reach the training window: "
                f"training_ticks={training_ticks!r}, limit={prediction_limit}"
            )
        return BpuBurstActivity(
            training_ticks=training_ticks,
            prediction_ticks=tuple(item.accepted_tick for item in observed),
            predictions=tuple(item.value for item in observed),
        )

    async def train_batches_with_prediction_pause(
        self, transactions: tuple[BpuBatchTraining, ...]
    ) -> tuple[int, ...]:
        """Queue distinct FTQ beats in a read-free predictor window.

        Return their hardware acceptance ticks so a scenario can assert its
        intended spacing. Input submission and acceptance ownership stay in
        the driver; tests need no event-loop task orchestration or pin access.
        """

        self._require_started()
        if not transactions:
            raise ValueError("BPU feedback burst must not be empty")
        old_prediction_ready = self._prediction_ready
        old_meta_ready = self._meta_ready
        await self.set_ready(prediction=False, meta=bool(old_meta_ready))
        try:
            await self.training_activity.wait_idle('reads')
            accepted = await self.train_batches(transactions)
            await self.training_activity.wait_idle('pipeline', 'writes')
            return accepted
        finally:
            await self.set_ready(
                prediction=bool(old_prediction_ready), meta=bool(old_meta_ready)
            )

    async def train_batch_with_prediction_pause(
        self, transaction: BpuBatchTraining, *, repetitions: int = 1
    ) -> None:
        """Train after single-port predictor reads have vacated their banks.

        ``train_batches`` remains available for active-stream races.
        This variant establishes a bounded read-free window for training that
        must read tagged predictor SRAMs, then lets pending writes commit.
        Multiple feedback beats share one such window.
        """

        self._require_started()
        if repetitions <= 0:
            raise ValueError("repetitions must be positive")
        old_prediction_ready = self._prediction_ready
        old_meta_ready = self._meta_ready
        await self.set_ready(prediction=False, meta=bool(old_meta_ready))
        try:
            await self.training_activity.wait_idle('reads')
            for _ in range(repetitions):
                await self.training_driver.send(transaction)
                await self.wait_training(committed=True)
            await self.training_activity.wait_idle('pipeline', 'writes')
        finally:
            await self.set_ready(
                prediction=bool(old_prediction_ready), meta=bool(old_meta_ready)
            )

    async def train_during_stream(
        self,
        transaction: BpuTraining,
        *,
        predictions: int = 16,
    ) -> BpuConcurrentActivity:
        """Train while independently collecting an active prediction stream."""

        self._require_stream_observation()
        if predictions <= 0:
            raise ValueError("prediction count must be positive")
        training = self.training_driver.send(self._single_training(transaction))
        observed = []
        try:
            for _ in range(predictions):
                observed.append(await self.prediction_monitor.recv())
            accepted = await training
        except BaseException:
            training.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await training
            raise
        await self.training_activity.wait_idle('pipeline')
        return BpuConcurrentActivity(
            training_tick=accepted.tick,
            prediction_ticks=tuple(item.accepted_tick for item in observed),
            predictions=tuple(item.value for item in observed),
        )

    async def redirect(self, transaction: BpuRedirect) -> int:
        self._require_started()
        if not isinstance(transaction, BpuRedirect):
            raise TypeError("BpuRedirect transaction required")
        payload = transaction.payload()
        if self._phr_observation is not None:
            return await self._phr_observation.redirect(payload)
        accepted = await self.redirect_driver.send(payload)
        return accepted.tick

    async def redirect_many(self, transactions) -> tuple[int, ...]:
        """Send adjacent recoveries and return their coherent acceptance ticks.

        The exclusive observation scope proves each complete input beat;
        neither a caller nor a driver completion guesses the accepted age.
        """
        self._require_started()
        transactions = tuple(transactions)
        if not transactions or any(not isinstance(tx, BpuRedirect) for tx in transactions):
            raise ValueError('a nonempty sequence of BpuRedirect transactions is required')
        if self._phr_observation is None:
            raise RuntimeError('adjacent recovery receipts require coherent PHR observation')
        payloads = tuple(tx.payload() for tx in transactions)
        return await self._phr_observation.redirect_many(payloads)

    async def redirect_and_settle(
        self, transaction: BpuRedirect, *, cycles: int | None = None
    ) -> int:
        """Move fetch away from a trained PC and retire older pipeline work."""

        if cycles is not None and cycles < 4:
            raise ValueError("settle needs at least four pipeline cycles")
        await self.redirect(transaction)
        if cycles is not None:
            return (await ClockCycles(self.dut.clock, cycles)).tick
        result = await wait_condition(self.dut.clock,
            sample=lambda: self.retirement_monitor._capture(None),
            satisfied=lambda state: state['valid'] and state['pc'] == transaction.pc,
            name=f'bpu.redirect_reaches_metadata.pc={transaction.pc:#x}',
            timeout_cycles=TRAINING_TIMEOUT_CYCLES)
        return result.tick

    async def wait_training(self, *, committed: bool = False):
        """Wait for FTQ feedback retirement; optionally require SRAM commit.

        Under active same-bank reads, buffers may legally remain pending.
        Tests needing commit should establish backpressure or use the paused
        training API, not insert a guessed delay after driver acceptance.
        """
        self._require_started()
        return await self.training_activity.wait_idle(*(('pipeline', 'writes') if committed else ('pipeline',)))

    def _control_values(self):
        return {
            "reset_vector": self._reset_vector,
            "prediction_ready": self._prediction_ready,
            "meta_ready": self._meta_ready,
            "ubtb_enable": self._predictor_enabled["ubtb"],
            "abtb_enable": self._predictor_enabled["abtb"],
            "mbtb_enable": self._predictor_enabled["mbtb"],
            "tage_enable": self._predictor_enabled["tage"],
            "sc_enable": self._predictor_enabled["sc"],
            "ittage_enable": self._predictor_enabled["ittage"],
            "ras_enable": self._predictor_enabled["ras"],
        }

    async def _drive_control(self, *, cycles: int = 1):
        return await self.control_driver.send(CycleTransaction(self._control_values(), cycles=cycles))

    async def accept_predictions_until(self, accepted, *, name, timeout_cycles=64, failure=None):
        """Accept through one declared monitor event, then close prediction flow.

        Intended for an already-drained protocol scope, which also owns the
        actual-acceptance receipt. Other controls and all accepted work are kept.
        """
        self._require_started()
        self._prediction_ready, self._meta_ready = 1, 1
        try:
            return await self.control_driver.send(PredictionWindow(
                self._control_values(), accepted, name, timeout_cycles, failure))
        finally:
            self._prediction_ready = 0

    async def allow_services_until(self, accepted, *, prepared, name, timeout_cycles=64, failure=None):
        """Stall prediction reads until compared service receipts, then resume.

        The observer owns the exact receipt and checks every service. Neither
        a fixed stall length nor a Python predicate determines this window.
        """
        self._require_started()
        if prepared is None:
            raise ValueError('service window requires a pre-edge preparation receipt for rise writes')
        self._prediction_ready, self._meta_ready = 0, 1
        try:
            return await self.control_driver.send(PredictionWindow(
                self._control_values(), accepted, name, timeout_cycles, failure,
                prediction_ready=False, prepared=prepared))
        finally:
            self._prediction_ready = 1

    _single_training = staticmethod(_single_training)

    _encode_training = staticmethod(_encode_training)

    _decode_prediction = staticmethod(_decode_prediction)

    _decode_meta = staticmethod(_decode_meta)

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("BPU agent requires an active Execution")

    def _require_stream_observation(self) -> None:
        self._require_started()
        if self._phr_observation is not None:
            raise RuntimeError(
                "coherent PHR observation owns the streams; use next_transaction"
            )
