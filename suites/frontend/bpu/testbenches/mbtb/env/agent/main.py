"""suites.frontend.bpu.testbenches.mbtb.env.agent.main components."""

from __future__ import annotations
from suites.frontend.bpu.testbenches.bpu.model.configuration import MAIN_WAYS
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
from typing import Any
from toffee import Bundle
from toffee import CheckContext
from toffee import ClockCycles
from suites.frontend.bpu.testbenches.shared.env.monitor.activity import ActivityMonitor
from suites.frontend.bpu.testbenches.mbtb.env.bundle.activity import training_activity
from suites.frontend.bpu.testbenches.shared.env.wait import wait_reset_done
from suites.frontend.bpu.testbenches.shared.env.wait import wait_condition
from toffee import Execution
from toffee import MISSING
from toffee import Scoreboard
from toffee import ScoreboardMode
from toffee import XTransfer
from toffee import TransferState
from suites.frontend.bpu.testbenches.shared.checker.prediction import compare_prediction
from suites.frontend.bpu.testbenches.mbtb.checker.semantic import MbtbSemanticChecker
from suites.frontend.bpu.testbenches.mbtb.checker.training_inputs import TrainingInputs
from suites.frontend.bpu.testbenches.mbtb.checker.lookup_inputs import LookupInputs
from suites.frontend.bpu.testbenches.mbtb.checker.prediction import MbtbPredictionScoreboard
from suites.frontend.bpu.testbenches.mbtb.env.monitor.semantic import MbtbSemanticMonitor
from suites.frontend.bpu.testbenches.mbtb.env.monitor.prediction import MbtbPredictionMonitor
from suites.frontend.bpu.testbenches.shared.env.driver.signal import AsyncSingleCycleDriver
from suites.frontend.bpu.testbenches.shared.env.driver.signal import ClockedWriteDriver
from suites.frontend.bpu.testbenches.shared.env.driver.signal import PulseDriver
from suites.frontend.bpu.testbenches.shared.env.driver.signal import ResetDriver
from suites.frontend.bpu.testbenches.shared.env.bundle.bindings import PortBinding
from suites.frontend.bpu.testbenches.shared.env.monitor.cycle import CycleMonitor
from suites.frontend.bpu.testbenches.mbtb.env.monitor.counter import MbtbCounterActivityMonitor
from suites.frontend.bpu.testbenches.mbtb.env.monitor.counter import MbtbCounterActivityTrace
from suites.frontend.bpu.testbenches.mbtb.model.counter import summarize_mbtb_counter_activity
from suites.frontend.bpu.testbenches.mbtb.env.driver.feedback import expected_mbtb_feedback
from suites.frontend.bpu.testbenches.mbtb.env.driver.feedback import observed_mbtb_feedback
from suites.frontend.bpu.testbenches.mbtb.env.monitor.entry import MbtbEntryActivityMonitor
from suites.frontend.bpu.testbenches.mbtb.env.monitor.entry import MbtbEntryActivityTrace
from suites.frontend.bpu.testbenches.mbtb.model.entry import summarize_mbtb_entry_activity
from suites.frontend.bpu.testbenches.mbtb.env.monitor.shadow import MbtbEntryShadowMonitor
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbBatchTraining
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbBranchFeedback
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbLookup
from suites.frontend.bpu.testbenches.mbtb.env.bundle.ports import MbtbPorts
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbPrediction
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbLookupDisposition
from suites.frontend.bpu.testbenches.shared.env.wait import RESET_TIMEOUT_CYCLES
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbTraining
from suites.frontend.bpu.testbenches.mbtb.env.monitor.decode import _decode
from suites.frontend.bpu.testbenches.mbtb.env.driver.encoding import _encode_branch_feedback
from suites.frontend.bpu.testbenches.mbtb.env.bundle.values import _plain


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
        self.reference = MbtbSemanticChecker()
        self.lookup_inputs=LookupInputs()
        self.training_inputs=TrainingInputs(validate_source=self.lookup_inputs.validate_training_source)
        self.prediction_monitor = MbtbPredictionMonitor(self.ports.prediction,self.lookup_inputs)
        self.reference_monitor = MbtbSemanticMonitor(dut, self.ports,
            training_inputs=self.training_inputs,lookup_inputs=self.lookup_inputs)
        self.prediction_scoreboard = MbtbPredictionScoreboard(self.lookup_inputs,self.reference,
            compare=self._compare_prediction)
        self._execution: Execution | None = None
        self._started = False
        self._finished = False
        self._finish_failure = None

    def _compare_prediction(self, expected, actual):
        # A scenario-specific assertion adds checks; it must not bypass an
        # already captured independent-model failure or leave it to teardown.
        self.reference.raise_failure()
        self.lookup_inputs.raise_failure()
        compare_prediction(expected, actual)

    def check_learning(self) -> None:
        """Surface a previously captured learning failure at a scenario cut."""
        self._require_started()
        self.reference.raise_failure()
        self.lookup_inputs.raise_failure()
        self.training_inputs.raise_failure()

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

    def _plan_lookup(self,transfer,*,input_only=False):
        self.lookup_inputs.plan(transfer.sequence_id,transfer.request,input_only=input_only)
        def terminal(handle):
            if handle.state is TransferState.CANCELLED:
                self.lookup_inputs.cancel_pending(handle.sequence_id,self._execution.backend.tick)
        transfer.add_done_callback(terminal)

    async def _advance_lookup(self, transfer,*,input_only=False):
        # One S1 and one S2 token per accepted S0 request. Continuous S2 fire
        # would repeatedly clean a stale SRAM read while a new victim arrives.
        try:
            launch=await transfer.wait_processing()
        except asyncio.CancelledError:
            if transfer.state is TransferState.CANCELLED:return
            raise
        uid=transfer.sequence_id
        self.lookup_inputs.launched(uid,launch.tick)
        if input_only:await ClockCycles(self.dut.clock,1)
        self.lookup_inputs.stage(uid,'advance')
        advanced=await self.advance_driver.send(None)
        self.lookup_inputs.stage_launched(uid,'advance',advanced.tick)
        deferred=self._defer_multi_hit_cleanup
        if deferred:
            self.lookup_inputs.defer_consume(uid)
        else:
            self.lookup_inputs.stage(uid,'consume')
        consumed=await self.consume_driver.send(None)
        if not deferred:
            self.lookup_inputs.stage_launched(uid,'consume',consumed.tick)

    async def launch_lookup(self, request):
        """Launch an acceptance-only query with the same real pipeline pulses.

        Reset tests observe its lease independently of the response scoreboard.
        """
        self._require_started()
        if type(request) is not MbtbLookup:raise ValueError('MainBTB launch requires a validated lookup')
        transfer=self.lookup_driver.send(request)
        self._plan_lookup(transfer,input_only=True)
        self._lookup_tails.add(asyncio.create_task(self._advance_lookup(transfer,input_only=True)))
        launch=await transfer
        self.reference.raise_failure()
        return launch

    async def _close_lookup_tails(self):
        tasks = tuple(self._lookup_tails)
        self._lookup_tails.clear()
        for task in tasks:
            if not task.done(): task.cancel()
        for task in tasks:
            try:
                with suppress(asyncio.CancelledError):await task
            except Exception as error:
                # A failed input check can also awaken the declared tail. Its
                # same already-observed failure is not an independent cleanup
                # error; unrelated stage/resource failures still propagate.
                if error is not self.reference.failure or not self.reference.failure_observed:
                    raise

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
        self.lookup_inputs.open_cleanup_scope()
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
                self.lookup_inputs.close_cleanup_scope()

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
        inputs=await self._issue_training((transaction,),encoded=(encoded,))
        await self._drain_multi_hit_cleanup()
        self._mark_training_drained(inputs)

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
            inputs=await self._issue_training((transaction,))
        finally:
            self._defer_multi_hit_cleanup=True
            self._quiesce_lookup()
            await monitor.aclose()
        if len(accepted)!=1:raise AssertionError('first-clear launch had no accepted normal feedback')
        await self._drain_multi_hit_cleanup()
        self.reference.raise_failure()
        self._mark_training_drained(inputs)

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

    async def finish(self,*,timeout_cycles=256):
        """Check autonomous completion without fabricating any functional input.

        Only the already-submitted S0/S1/S2 tails may run. No reset, enable,
        training, metadata or synthetic consume is added to pay off a debt.
        Closing monitors or dropping views is never a completion event.
        """
        if type(timeout_cycles) is not int or timeout_cycles<=0:
            raise ValueError('MainBTB finish requires a positive cycle budget')
        if self._finish_failure is not None:raise self._finish_failure
        self._require_started(allow_finished=True)
        try:
            self.reference.raise_failure()
            if self._finished:return self.receipt()
            if any((self._multi_hit_cleanup_scope_active,self._counter_activity_active,
                    self._entry_activity_active,self._entry_shadow_active)):
                raise AssertionError('MainBTB finish requires all explicit observation/cleanup scopes to exit')
            if len(self.reference_monitor.subscriptions)!=2:
                raise AssertionError('MainBTB finish requires the continuous input and output monitors')
            deadline=self._execution.backend.tick+2*timeout_cycles

            def remaining():
                cycles=(deadline-self._execution.backend.tick)//2
                if cycles<=0:raise TimeoutError('MainBTB finish cycle budget exhausted')
                return cycles

            await self.drain_predictions(timeout_cycles=remaining())
            await self.training_activity.wait_idle(timeout_cycles=remaining())
            await self.prediction_scoreboard.finish(timeout_cycles=remaining(),observe_cycles=2)
            self.reference.raise_failure()
            model=self.reference.model
            pending=dict(entries=sum(len(cache.outstanding) for cache in model.entries.values()),
                directions=sum(len(queue.pending) for queue in model.directions.values()),
                snapshots=len(model.snapshots),cleanup=len(model.cleanup),
                entry_offers=sum(len(offers) for offers in model.entry_offers.values()),
                feedback=int(model.offered is not None))
            if any(pending.values()):raise AssertionError(f'MainBTB finish has outstanding semantic work: {pending}')
            self.training_inputs.drained(self._execution.backend.tick,
                tuple(row.uid for row in self.training_inputs.rows if row.state=='accepted'))
            self.training_inputs.finish()
            self.lookup_inputs.finish()
            self._finished=True
            return self.receipt()
        except BaseException as error:
            self._finish_failure=error
            raise

    def receipt(self):
        lookups=self.lookup_inputs.receipt()
        return dict(finished=self._finished,reference_checks=self.reference.board.status.checked,
            reference_failures=self.reference.board.status.failed,
            prediction=self.prediction_scoreboard.status,
            accepted_feedback=self.reference.model.accepted_feedback,
            entry_commits=self.reference.model.entry_commits,counter_commits=self.reference.model.counter_commits,
            training_inputs=self.training_inputs.receipt(),lookup_inputs=lookups,
            lookup_deliveries=dict(effective_responses=sum(row['response_tick'] is not None for row in lookups),
                checked_sdk_results=sum(row['delivery_tick'] is not None for row in lookups),
                non_response_terminals=sum(row['delivery_tick'] is not None and row['response_tick'] is None for row in lookups)))

    async def aclose(self,*,check=True) -> None:
        if type(check) is not bool:raise ValueError('MainBTB close check must be a semantic bool')
        if not self._started:
            if check and self._finish_failure is not None:raise self._finish_failure
            return
        primary=None;errors=[]
        try:
            if check:await self.finish()
        except BaseException as error:
            primary=error
        finally:
            # Every resource is released even if a different cleanup fails.
            for close in (self.prediction_scoreboard.aclose,self.reference_monitor.aclose,
                    self._close_lookup_tails,self.advance_driver.aclose,
                    self.consume_driver.aclose,self.lookup_driver.aclose):
                try:await close()
                except BaseException as error:errors.append(error)
            for close in (self.training_driver.close,self.control_driver.close,self.reset_driver.close):
                try:close()
                except BaseException as error:errors.append(error)
            self._execution = None
            self._started = False
        if primary is not None:
            if errors:raise BaseExceptionGroup('MainBTB finish and independent cleanup failures',[primary,*errors])
            raise primary
        if len(errors)==1:raise errors[0]
        if errors:raise BaseExceptionGroup('MainBTB independent cleanup failures',errors)

    async def reset(self, cycles: int = 3) -> int:
        self._require_started()
        if type(cycles) is not int or cycles<=0:raise ValueError('MainBTB reset requires a positive integer cycle count')
        await self.reset_driver.send(cycles)
        await self.set_enabled(True)
        def sample():
            failure=self.prediction_scoreboard.status.first_failure
            if failure is not None:raise failure
            self.reference.raise_failure()
            status=self.ports.status.bits.sample()
            return dict(reset_done=status.reset_done.as_int(),train_ready=status.train_ready.as_int())
        try:
            done=await wait_condition(self.dut.clock,sample=sample,
                satisfied=lambda value:value['reset_done']==1,name='mbtb.reset-done',timeout_cycles=RESET_TIMEOUT_CYCLES)
        except BaseException:
            if self.prediction_scoreboard.status.first_failure is not None:
                # Public SDK observation boundary, not private failure flags or
                # discarded queued samples. Abort a long reset wait promptly.
                await self.prediction_scoreboard.drain(timeout_cycles=1)
            raise
        if not done.state['train_ready']:
            raise AssertionError("MainBTB training port is not ready")
        return done.samples

    async def set_enabled(self, enabled: bool) -> None:
        """Control the global lookup/training gate independently of requests."""

        self._require_started()
        if type(enabled) is not bool:raise ValueError('MainBTB enable requires a semantic bool')
        await self.control_driver.send({"enable": int(enabled)})

    async def sample_prediction(self) -> MbtbPrediction:
        """Return a clocked output snapshot when the pipeline is not advancing."""

        self._require_started()
        event = await ClockCycles(self.dut.clock, 1)
        value = self.prediction_monitor.sample_at(event).value
        self.reference.raise_failure()
        return value.preview if type(value) is MbtbLookupDisposition else value

    def submit_predict(
        self, pc: int, *, expected: Any = MISSING
    ) -> XTransfer[MbtbLookup, MbtbPrediction | MbtbLookupDisposition]:
        self._require_started()
        transfer = self.prediction_scoreboard.submit(MbtbLookup(pc), expected=expected)
        self._plan_lookup(transfer)
        self._lookup_tails.add(asyncio.create_task(self._advance_lookup(transfer)))
        return transfer

    async def drain_predictions(self,*,timeout_cycles=64):
        if type(timeout_cycles) is not int or timeout_cycles<=0:
            raise ValueError('MainBTB drain requires a positive cycle budget')
        deadline=self._execution.backend.tick+2*timeout_cycles
        result = await self.prediction_scoreboard.drain(timeout_cycles=timeout_cycles)
        # Input-stage completions awakened at the response edge need task
        # dispatch, not an extra DUT edge. Advancing first creates a legitimate
        # idle sample in the SDK's sampled stream and breaks raw queue status.
        # Never close the monitor or clear its observations to repair that.
        async with self._execution.paused():
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        if self._lookup_tails and not all(task.done() for task in self._lookup_tails):
            remaining=(deadline-self._execution.backend.tick)//2
            if remaining<=0:raise TimeoutError('MainBTB lookup tails did not finish within the drain budget')
            await wait_condition(self.dut.clock,sample=lambda:all(task.done() for task in self._lookup_tails),
                satisfied=bool,name='mbtb.input-stage-tails',timeout_cycles=remaining)
        while self._lookup_tails:
            task = next(iter(self._lookup_tails))
            try:
                await task
            finally:
                self._lookup_tails.discard(task)
        self.reference.raise_failure()
        return result

    async def predict(self, pc: int) -> MbtbPrediction | MbtbLookupDisposition:
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
        inputs=await self._pulse_training(transaction)
        await self.training_activity.wait_idle()
        self.reference.raise_failure()
        self._mark_training_drained(inputs)

    async def train_burst(
        self, transactions: tuple[MbtbBatchTraining, ...]
    ) -> None:
        """Send consecutive FTQ feedback beats, then let writes settle once."""

        self._require_started()
        if not transactions:
            raise ValueError("MainBTB training burst must not be empty")
        inputs=await self._issue_training(tuple(transactions))
        await self.training_activity.wait_idle()
        self.reference.raise_failure()
        self._mark_training_drained(inputs)

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

    async def _issue_training(self,transactions,*,encoded=None):
        self._require_started();transactions=tuple(transactions)
        async with self.training_driver.resource_lock('mbtb.planned-feedback'):
            inputs=self.training_inputs.plan(transactions)
            try:
                values=(tuple(self._encode_training(tx) for tx in transactions) if encoded is None else encoded)
                await self.training_driver.send_many(values)
                self.reference.raise_failure()
            except asyncio.CancelledError:
                self.training_inputs.cancel_inputs(inputs,at=self._execution.backend.tick)
                raise
            except BaseException as error:
                self.training_inputs.fail(error)
                if self.reference.failure is None:self.reference.failure=error
                raise
            return inputs

    def _mark_training_drained(self,inputs):
        self.reference.raise_failure()
        self.training_inputs.drained(self._execution.backend.tick,inputs)

    async def issue_training(self,transaction):
        """Issue one immutable feedback without draining its autonomous writes.

        Reset/lifetime scenarios use this instead of bypassing the input plan
        through the physical driver. The returned IDs are not response tags.
        """
        return await self._issue_training((transaction,))

    async def _pulse_training(self, transaction: MbtbBatchTraining):
        return await self.issue_training(transaction)

    def _encode_training(self, transaction: MbtbBatchTraining) -> dict[str, Any]:
        self._require_started()
        branch_count = len(self.ports.training.bits.branches)
        if not 1 <= len(transaction.branches) <= branch_count:
            raise ValueError(f"MainBTB feedback requires 1 to {branch_count} branches")
        if sum(bool(branch.mispredict) for branch in transaction.branches if branch is not None) > 1:
            raise ValueError("MainBTB feedback permits at most one mispredicted branch")
        branches = transaction.branches + (None,) * (branch_count - len(transaction.branches))
        return {
            "start_pc0": transaction.pc,
            # Pc.addr omits architectural bit 0; DefaultConfig alignment
            # is 32 bytes (16 halfwords).
            "start_pc1": ((transaction.pc & ~0xf) + 0x10) % (1 << 49),
            # Fifth-slot training consumes only exposed identity, not the
            # prediction counter. Never infer a missing victim as a miss.
            "meta_entries": tuple(
                tuple(dict(entry) if way<MAIN_WAYS else
                      dict(rawHit=entry['rawHit'],position=entry['position'])
                      for way,entry in enumerate(row))
                for row in transaction.meta_entries),
            "branches": tuple(_encode_branch_feedback(branch) for branch in branches),
        }

    _decode = staticmethod(_decode)

    def _require_started(self,*,allow_finished=False) -> None:
        if not self._started:
            raise RuntimeError("MainBTB agent requires an active Execution")
        if self._finished and not allow_finished:
            raise RuntimeError('MainBTB agent has finished; no further transactions are permitted')
