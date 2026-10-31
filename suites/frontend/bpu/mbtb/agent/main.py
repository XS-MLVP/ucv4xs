"""suites.frontend.bpu.mbtb.agent.main components."""

from __future__ import annotations
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
from typing import Any
from toffee import Bundle
from toffee import CheckContext
from toffee import ClockCycles
from suites.frontend.bpu.monitors.activity import ActivityMonitor
from suites.frontend.bpu.mbtb.bundle.activity import training_activity
from suites.frontend.bpu.runtime.wait import wait_reset_done
from toffee import Execution
from toffee import MISSING
from toffee import Scoreboard
from toffee import ScoreboardMode
from toffee import XTransfer
from suites.frontend.bpu.checkers.prediction import compare_prediction
from suites.frontend.bpu.mbtb.checker.semantic import MbtbSemanticChecker
from suites.frontend.bpu.mbtb.monitor.semantic import MbtbSemanticMonitor
from suites.frontend.bpu.drivers.signal import AsyncSingleCycleDriver
from suites.frontend.bpu.drivers.signal import ClockedWriteDriver
from suites.frontend.bpu.drivers.signal import PulseDriver
from suites.frontend.bpu.drivers.signal import ResetDriver
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.mbtb.monitor.counter import MbtbCounterActivityMonitor
from suites.frontend.bpu.mbtb.monitor.counter import MbtbCounterActivityTrace
from suites.frontend.bpu.mbtb.model.counter import summarize_mbtb_counter_activity
from suites.frontend.bpu.mbtb.driver.feedback import expected_mbtb_feedback
from suites.frontend.bpu.mbtb.driver.feedback import observed_mbtb_feedback
from suites.frontend.bpu.mbtb.monitor.entry import MbtbEntryActivityMonitor
from suites.frontend.bpu.mbtb.monitor.entry import MbtbEntryActivityTrace
from suites.frontend.bpu.mbtb.model.entry import summarize_mbtb_entry_activity
from suites.frontend.bpu.mbtb.monitor.shadow import MbtbEntryShadowMonitor
from suites.frontend.bpu.mbtb.transaction.types import MbtbBatchTraining
from suites.frontend.bpu.mbtb.transaction.types import MbtbBranchFeedback
from suites.frontend.bpu.mbtb.transaction.types import MbtbLookup
from suites.frontend.bpu.mbtb.bundle.ports import MbtbPorts
from suites.frontend.bpu.mbtb.transaction.types import MbtbPrediction
from suites.frontend.bpu.mbtb.transaction.types import MbtbTraining
from suites.frontend.bpu.mbtb.monitor.decode import _decode
from suites.frontend.bpu.mbtb.driver.encoding import _encode_branch_feedback
from suites.frontend.bpu.mbtb.bundle.values import _plain


class MbtbAgent:
    """Own MainBTB lookup, feedback and independent semantic checking."""

    def __init__(self, dut: Any) -> None:
        self.dut = dut
        self.ports = MbtbPorts.bind(dut)
        self.training_activity = ActivityMonitor(training_activity(dut))
        self._defer_multi_hit_cleanup = False
        self._multi_hit_cleanup_scope_active = False
        self._counter_monitor = self._counter_input_monitor = None
        self._counter_activity_active = False
        self._entry_monitor = self._entry_input_monitor = None
        self._entry_activity_active = False
        self._entry_shadow_monitor = None
        self._entry_shadow_active = False
        self.feedback_scoreboard = Scoreboard('mbtb.feedback')
        self.counter_scoreboard = Scoreboard('mbtb.counter_activity')
        self.entry_scoreboard = Scoreboard('mbtb.entry_activity')
        self.reset_driver = ResetDriver(dut)
        self.control_driver = ClockedWriteDriver(self.ports.control)
        self.lookup_driver = AsyncSingleCycleDriver(
            PortBinding(dut.clock, Bundle(s0_fire=self.ports.lookup.bits.s0_fire,
                start_pc=self.ports.lookup.bits.start_pc, s3_fire=self.ports.lookup.bits.s3_fire,
                victim_taken=self.ports.lookup.bits.victim_taken), 'mbtb.lookup_s0'),
            idle=self._lookup_idle,
            encoder=self._encode_lookup,
        )
        self.advance_driver = AsyncSingleCycleDriver(
            PortBinding(dut.clock, Bundle(fire=self.ports.lookup.bits.s1_fire), 'mbtb.lookup_s1'),
            idle={'fire': 0}, encoder=lambda _: {'fire': 1})
        self.consume_driver = AsyncSingleCycleDriver(
            PortBinding(dut.clock, Bundle(fire=self.ports.lookup.bits.s2_fire), 'mbtb.lookup_s2'),
            idle=lambda _: {'fire': int(self._multi_hit_cleanup_scope_active and not self._defer_multi_hit_cleanup)},
            encoder=lambda _: {'fire': int(not self._defer_multi_hit_cleanup)})
        self._lookup_tails = set()
        self.training_driver = PulseDriver(self.ports.training)
        self.prediction_monitor = CycleMonitor(
            self.ports.prediction, decoder=self._decode
        )
        self.reference = MbtbSemanticChecker()
        self.reference_monitor = MbtbSemanticMonitor(dut, self.ports)
        self.prediction_scoreboard = Scoreboard(
            "mbtb.prediction",
            compare=self._compare_prediction,
            expected=self.reference.response_expected,
        )
        self._execution: Execution | None = None
        self._started = False

    def _compare_prediction(self, expected, actual):
        # A scenario-specific assertion adds checks; it must not bypass an
        # already captured independent-model failure or leave it to teardown.
        self.reference.raise_failure()
        compare_prediction(expected, actual)

    def _lookup_idle(self, _last_request: MbtbLookup | None) -> dict[str, int]:
        return {
            "s0_fire": 0,
            "s3_fire": 0,
            "victim_taken": (0, 0),
            "start_pc": 0,
        }

    def _encode_lookup(self, request: MbtbLookup) -> dict[str, int]:
        return {
            "s0_fire": 1,
            "s3_fire": 0,
            "victim_taken": (0, 0),
            "start_pc": request.pc,
        }

    def _quiesce_lookup(self):
        self.lookup_driver.quiesce()
        self.consume_driver.quiesce()

    async def _advance_lookup(self, transfer):
        # One S1 and one S2 token per accepted S0 request. Continuous S2 fire
        # would repeatedly clean a stale SRAM read while a new victim arrives.
        await transfer.wait_processing()
        await self.advance_driver.send(None)
        await self.consume_driver.send(None)

    async def launch_lookup(self, request):
        """Launch an acceptance-only query with the same real pipeline pulses.

        Reset tests observe its lease independently of the response scoreboard.
        """
        launch = await self.lookup_driver.send(request)
        async def advance():
            await ClockCycles(self.dut.clock, 1)
            await self.advance_driver.send(None)
            await self.consume_driver.send(None)
        self._lookup_tails.add(asyncio.create_task(advance()))
        return launch

    async def _close_lookup_tails(self):
        tasks = tuple(self._lookup_tails)
        self._lookup_tails.clear()
        for task in tasks:
            if not task.done(): task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task

    @asynccontextmanager
    async def defer_multi_hit_cleanup(self) -> AsyncIterator[None]:
        """Expose a transient duplicate prediction before the S2 flush runs.

        Training and prediction still use their normal drivers. The caller
        observes the public result while cleanup is held; leaving this scope
        restores S2 fire and gives the single-port SRAM time to apply the
        queued flush before a subsequent lookup.
        """

        self._require_started()
        if self._multi_hit_cleanup_scope_active:
            raise RuntimeError("MainBTB multi-hit cleanup is already deferred")
        self._multi_hit_cleanup_scope_active = True
        self._defer_multi_hit_cleanup = True
        self._quiesce_lookup()
        try:
            yield
        finally:
            self._defer_multi_hit_cleanup = False
            self._quiesce_lookup()
            try:
                # One S2 pulse accepts the cached result; retirement below
                # follows registered clear requests and pending SRAM writes.
                await ClockCycles(self.dut.clock, 1)
                await self._drain_multi_hit_cleanup()
            finally:
                self._multi_hit_cleanup_scope_active = False
                self.consume_driver.quiesce()

    async def train_during_multi_hit_cleanup(
        self, transaction: MbtbBatchTraining, *, shadow_state: str = "dirty"
    ) -> None:
        """Resume cached S2 cleanup while a normal feedback beat advances.

        A clean-shadow control first pulses S2 once, pauses it and retires that
        clear. The later clear can then hit an unchanged, clean entry while
        training another SRAM set. Stage timing belongs here, not in tests.
        This requires an active defer_multi_hit_cleanup scope; it does not
        claim that replayed metadata is reachable through the integrated FTQ.
        """
        self._require_started()
        if not self._multi_hit_cleanup_scope_active or not self._defer_multi_hit_cleanup:
            raise RuntimeError("cleanup training requires an active deferred cleanup scope")
        if shadow_state not in ("dirty", "clean"):
            raise ValueError("cleanup shadow state must be dirty or clean")
        encoded = self._encode_training(transaction)
        if shadow_state == "clean":
            self._defer_multi_hit_cleanup = False
            self._quiesce_lookup()
            try:
                await ClockCycles(self.dut.clock, 1)
            finally:
                self._defer_multi_hit_cleanup = True
                self._quiesce_lookup()
            await self.training_activity.wait_idle('pipeline', 'writes')
        self._defer_multi_hit_cleanup = False
        self._quiesce_lookup()
        await self.training_driver.send(encoded)
        await self._drain_multi_hit_cleanup()

    async def retire_multi_hit_cleanup(self) -> None:
        """Retire queued clears after a fresh lookup replaces cached multi-hit."""
        self._require_started()
        await self._drain_multi_hit_cleanup()

    async def train_with_first_multi_hit_cleanup(self, transaction: MbtbBatchTraining) -> None:
        """Align the first clear with correction, not a replayed earlier clear.

        A public accepted-feedback observation releases the one-shot S2
        consume pulse. This is an event handoff, not a settling delay;
        the caller's passive monitor must prove the two requests met.
        No test needs to know clock phases or manipulate stage-control IO.
        """
        self._require_started()
        if not self._multi_hit_cleanup_scope_active or not self._defer_multi_hit_cleanup:
            raise RuntimeError('first-clear collision needs a deferred genuine duplicate')
        accepted=[]
        monitor=CycleMonitor(PortBinding(self.dut.clock,Bundle(valid=self.ports.training.valid,
            ready=self.ports.status.bits.train_ready),'mbtb.first-clear-admission'),
            decoder=lambda v:dict(valid=v.valid.as_int(),ready=v.ready.as_int()))
        def release(frame):
            if frame.value['valid'] and frame.value['ready']:
                if accepted:raise AssertionError('first-clear launch requires exactly one feedback acceptance')
                accepted.append(frame.event.tick)
                self._defer_multi_hit_cleanup=False
                self._quiesce_lookup()
        monitor.start(self._execution,observer=release)
        try:
            await self.training_driver.send(self._encode_training(transaction))
        finally:
            self._defer_multi_hit_cleanup=True
            self._quiesce_lookup()
            await monitor.aclose()
        if len(accepted)!=1:raise AssertionError('first-clear launch had no accepted normal feedback')
        await self._drain_multi_hit_cleanup()
        self.reference.raise_failure()

    async def _drain_multi_hit_cleanup(self) -> None:
        """Stop replaying cached S2 clears while their actual writes retire."""
        old_defer = self._defer_multi_hit_cleanup
        self._defer_multi_hit_cleanup = True
        self._quiesce_lookup()
        try:
            await self.training_activity.wait_idle('pipeline', 'writes')
        finally:
            self._defer_multi_hit_cleanup = old_defer
            self._quiesce_lookup()

    async def start(self, execution: Execution) -> "MbtbAgent":
        if self._started:
            raise RuntimeError("MainBTB agent is already started")
        self._execution = execution
        self.reference_monitor.start(execution, self.reference)
        await self.reset_driver.__aenter__()
        try:
            await self.control_driver.__aenter__()
            self.lookup_driver.start(execution)
            self.advance_driver.start(execution)
            self.consume_driver.start(execution)
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
        except BaseException:
            await self.reference_monitor.aclose()
            await self._close_lookup_tails()
            await self.advance_driver.aclose()
            await self.consume_driver.aclose()
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
            self.training_driver.close()
            await self._close_lookup_tails()
            await self.advance_driver.aclose()
            await self.consume_driver.aclose()
            await self.lookup_driver.aclose()
            self.control_driver.close()
            self.reset_driver.close()
            self._execution = None
            self._started = False
        self.reference.raise_unobserved_failure()

    async def reset(self, cycles: int = 3) -> int:
        self._require_started()
        await self.reset_driver.send(cycles)
        await self.set_enabled(True)
        waited = (await wait_reset_done(self.ports.status)).samples
        status = self.ports.status.bits.sample()
        if not status.train_ready.as_int():
            raise AssertionError("MainBTB training port is not ready")
        return waited

    async def set_enabled(self, enabled: bool) -> None:
        """Control the global lookup/training gate independently of requests."""

        self._require_started()
        await self.control_driver.send({"enable": int(enabled)})

    async def sample_prediction(self) -> MbtbPrediction:
        """Return a clocked output snapshot when the pipeline is not advancing."""

        self._require_started()
        event = await ClockCycles(self.dut.clock, 1)
        value = self.prediction_monitor.sample_at(event).value
        self.reference.raise_failure()
        return value

    def submit_predict(
        self, pc: int, *, expected: Any = MISSING
    ) -> XTransfer[MbtbLookup, MbtbPrediction]:
        self._require_started()
        transfer = self.prediction_scoreboard.submit(MbtbLookup(pc), expected=expected)
        self._lookup_tails.add(asyncio.create_task(self._advance_lookup(transfer)))
        return transfer

    async def drain_predictions(self):
        result = await self.prediction_scoreboard.drain(timeout_cycles=64)
        while self._lookup_tails:
            task = next(iter(self._lookup_tails))
            try:
                await task
            finally:
                self._lookup_tails.discard(task)
        self.reference.raise_failure()
        return result

    async def predict(self, pc: int) -> MbtbPrediction:
        return await self.submit_predict(pc)

    async def train(self, transaction: MbtbTraining) -> None:
        await self.train_batch(
            MbtbBatchTraining(
                pc=transaction.pc,
                meta_entries=transaction.meta_entries,
                branches=(
                    MbtbBranchFeedback(
                        target=transaction.target,
                        taken=transaction.taken,
                        position=transaction.position,
                        branch_type=transaction.branch_type,
                        ras_action=transaction.ras_action,
                        mispredict=transaction.mispredict,
                    ),
                ),
            )
        )

    async def train_batch(self, transaction: MbtbBatchTraining) -> None:
        await self._pulse_training(transaction)
        await self.training_activity.wait_idle()
        self.reference.raise_failure()

    async def train_burst(
        self, transactions: tuple[MbtbBatchTraining, ...]
    ) -> None:
        """Send consecutive FTQ feedback beats, then let writes settle once."""

        self._require_started()
        if not transactions:
            raise ValueError("MainBTB training burst must not be empty")
        await self.training_driver.send_many(
            tuple(self._encode_training(transaction) for transaction in transactions)
        )
        await self.training_activity.wait_idle()
        self.reference.raise_failure()

    @asynccontextmanager
    async def observe_counter_activity(self):
        if not self._started or self._execution is None:
            raise RuntimeError('counter observation requires a started MainBTB agent')
        if self._counter_activity_active or getattr(self, '_entry_activity_active', False):
            raise RuntimeError('MainBTB counter observation is already active')
        if self._counter_monitor is None:
            self._counter_monitor = MbtbCounterActivityMonitor(self.dut)
        if self._counter_input_monitor is None:
            self._counter_input_monitor = CycleMonitor(PortBinding(self.dut.clock,Bundle(
                valid=self.ports.training.valid,ready=self.ports.status.bits.train_ready,
                bits=self.ports.training.bits),'mbtb.feedback_observation'),decoder=_plain)
        trace = MbtbCounterActivityTrace()
        self._counter_activity_active = True
        try:
            self._counter_monitor.start(self._execution,observer=trace.frames.append)
            self._counter_input_monitor.start(self._execution,observer=lambda frame:
                trace.feedback.append(frame) if frame.value['valid'] else None)
            yield trace
        finally:
            try:
                await self._counter_input_monitor.aclose()
            finally:
                try:
                    await self._counter_monitor.aclose()
                finally:
                    self._counter_activity_active = False

    async def train_during_predictions_checked(self, transactions, lookups, trace,
                                               *, expected_activity, mode):
        """Overlap a feedback burst and submitted predictions, then compare IO.

        The synchronous pulse source does not expose XTransfer acceptance.
        Its actual accepted inputs come from the passive IO monitor; prediction
        transfers retain the existing asynchronous driver/monitor Scoreboard.
        """
        if not transactions or not lookups:
            raise ValueError('counter overlap requires feedback and prediction submissions')
        if not self._counter_activity_active:
            raise RuntimeError('checked counter overlap requires active observation')
        if mode not in ('blocked','flow'):
            raise ValueError('counter overlap mode must be blocked or flow')
        await self._train_activity_checked(transactions, lookups, trace, expected_activity=expected_activity,
            mode=mode, scoreboard=self.counter_scoreboard, label='mbtb.counter_activity',
            summarize=summarize_mbtb_counter_activity)

    @asynccontextmanager
    async def observe_entry_shadow(self):
        """Observe retained owner/depth without changing any internal state."""
        self._require_started()
        if self._entry_shadow_active:
            raise RuntimeError('MainBTB entry shadow observation is already active')
        if self._entry_shadow_monitor is None:
            self._entry_shadow_monitor = MbtbEntryShadowMonitor(self.dut)
        frames = []
        self._entry_shadow_active = True
        try:
            self._entry_shadow_monitor.start(self._execution, observer=frames.append)
            yield frames
        finally:
            try:
                await self._entry_shadow_monitor.aclose()
            finally:
                self._entry_shadow_active = False

    @asynccontextmanager
    async def observe_entry_activity(self):
        if not self._started or self._execution is None:
            raise RuntimeError('entry observation requires a started MainBTB agent')
        if self._entry_activity_active or getattr(self, '_counter_activity_active', False):
            raise RuntimeError('MainBTB training activity observation is already active')
        if self._entry_monitor is None:
            self._entry_monitor = MbtbEntryActivityMonitor(self.dut)
        if self._entry_input_monitor is None:
            self._entry_input_monitor = CycleMonitor(PortBinding(self.dut.clock, Bundle(
                valid=self.ports.training.valid, ready=self.ports.status.bits.train_ready,
                bits=self.ports.training.bits), 'mbtb.entry_feedback_observation'), decoder=_plain)
        trace = MbtbEntryActivityTrace()
        self._entry_activity_active = True
        try:
            self._entry_monitor.start(self._execution, observer=trace.frames.append)
            self._entry_input_monitor.start(self._execution, observer=lambda frame:
                trace.feedback.append(frame) if frame.value['valid'] else None)
            yield trace
        finally:
            try:
                await self._entry_input_monitor.aclose()
            finally:
                try:
                    await self._entry_monitor.aclose()
                finally:
                    self._entry_activity_active = False

    async def train_entry_during_predictions_checked(self, transactions, lookups, trace,
                                                     *, expected_activity, mode):
        if not transactions or not lookups:
            raise ValueError('entry overlap requires feedback and prediction submissions')
        if not self._entry_activity_active:
            raise RuntimeError('checked entry overlap requires active observation')
        if mode not in ('blocked', 'flow'):
            raise ValueError('entry overlap mode must be blocked or flow')
        await self._train_activity_checked(transactions, lookups, trace, expected_activity=expected_activity,
            mode=mode, scoreboard=self.entry_scoreboard, label='mbtb.entry_activity',
            summarize=summarize_mbtb_entry_activity)

    async def _train_activity_checked(self, transactions, lookups, trace, *, expected_activity,
                                      mode, scoreboard, label, summarize):
        expected_input = tuple(expected_mbtb_feedback(transaction,
                               branch_count=len(self.ports.training.bits.branches)) for transaction in transactions)
        expected = deepcopy(expected_activity)
        first_input,first_frame = len(trace.feedback),len(trace.frames)
        await self.train_burst(tuple(transactions))
        await self.drain_predictions()
        # Retire the last writeback and passive deliveries before closing scope.
        await ClockCycles(self.dut.clock,2)
        accepted,frames = trace.feedback[first_input:],trace.frames[first_frame:]
        context = dict(mode=ScoreboardMode.DIRECT,sequence_id=first_input+1,request=tuple(transactions),
                       accepted_event=accepted[0].event if accepted else None,
                       observed_event=frames[-1].event if frames else None)
        self.feedback_scoreboard.check(
            expected={'beats':len(transactions),'frames':expected_input,'adjacent':True},
            actual={'beats':len(accepted),'frames':tuple(observed_mbtb_feedback(frame.value) for frame in accepted),
                    'adjacent':all(after.event.tick-before.event.tick==2 for before,after in zip(accepted,accepted[1:]))},
            context=CheckContext(scoreboard='mbtb.feedback',**context))
        scoreboard.check(expected=expected, actual=summarize(frames, accepted, lookups, mode),
                         context=CheckContext(scoreboard=label, **context))

    async def _pulse_training(self, transaction: MbtbBatchTraining) -> None:
        await self.training_driver.send(self._encode_training(transaction))

    def _encode_training(self, transaction: MbtbBatchTraining) -> dict[str, Any]:
        self._require_started()
        branch_count = len(self.ports.training.bits.branches)
        if not 1 <= len(transaction.branches) <= branch_count:
            raise ValueError(f"MainBTB feedback requires 1 to {branch_count} branches")
        if sum(bool(branch.mispredict) for branch in transaction.branches) > 1:
            raise ValueError("MainBTB feedback permits at most one mispredicted branch")
        branches = transaction.branches + (None,) * (branch_count - len(transaction.branches))
        return {
            "start_pc0": transaction.pc,
            # Pc.addr omits architectural bit 0; DefaultConfig alignment
            # is 32 bytes (16 halfwords).
            "start_pc1": (transaction.pc & ~0xf) + 0x10,
            # The whole-chip training port keeps the four aligned ways per
            # bank; the victim's metadata sideband is only a prediction output.
            "meta_entries": tuple(
                tuple(row[:len(binding_bank)])
                for row, binding_bank in zip(
                    transaction.meta_entries,
                    self.ports.training.bits.meta_entries, strict=True)),
            "branches": tuple(_encode_branch_feedback(branch) for branch in branches),
        }

    _decode = staticmethod(_decode)

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("MainBTB agent requires an active Execution")
