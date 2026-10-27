"""bpuverify.tage.agent.main components."""

from __future__ import annotations
import asyncio
from contextlib import suppress
from copy import deepcopy
from contextlib import asynccontextmanager
from typing import Any
from typing import Sequence
from toffee import Bundle
from toffee import CheckContext
from toffee import ClockCycles
from toffee import Execution
from toffee import MISSING
from toffee import Scoreboard
from toffee import ScoreboardMode
from toffee import XTransfer
from bpuverify.common.checker.prediction import compare_prediction
from bpuverify.tage.checker.semantic import TageSemanticChecker
from bpuverify.tage.monitor.semantic import TageSemanticMonitor
from bpuverify.common.model.folded_history import folded_history_values, PHR_FOLD_LAYOUT, validate_folded_history_layout
from toffee.signals import signal_width
from bpuverify.common.driver.signal import AsyncSingleCycleDriver
from bpuverify.common.driver.signal import ClockedWriteDriver
from bpuverify.common.driver.signal import PulseDriver
from bpuverify.common.driver.signal import ResetDriver
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.monitor.cycle import CycleMonitor
from bpuverify.common.monitor.activity import ActivityMonitor
from bpuverify.tage.bundle.activity import training_activity
from bpuverify.common.env.wait import wait_reset_done
from bpuverify.tage.driver.feedback import expected_tage_feedback
from bpuverify.tage.driver.feedback import observed_tage_feedback
from bpuverify.tage.monitor.state import TagePredictionStateMonitor
from bpuverify.tage.monitor.state import TageSelectorMonitor
from bpuverify.tage.monitor.write import TageWriteActivityMonitor
from bpuverify.tage.monitor.shadow import TageShadowMonitor
from bpuverify.tage.transaction.types import TageBaseBranch
from bpuverify.tage.transaction.types import TageBatchTraining
from bpuverify.tage.transaction.types import TageBranchFeedback
from bpuverify.tage.transaction.types import TageLookup
from bpuverify.tage.bundle.ports import TagePorts
from bpuverify.tage.transaction.types import TagePrediction
from bpuverify.tage.transaction.types import TageTraining
from bpuverify.tage.driver.encoding import _base_counter
from bpuverify.tage.monitor.decode import _decode
from bpuverify.tage.driver.encoding import _encode_branch_feedback
from bpuverify.tage.driver.encoding import _main_btb
from bpuverify.tage.bundle.values import _plain


class TageAgent:
    def __init__(self, dut: Any) -> None:
        self.dut = dut
        self.ports = TagePorts.bind(dut)
        self.training_activity = ActivityMonitor(training_activity(dut))
        self._main_btb_capacity = len(self.ports.lookup.bits.main_btb.result)
        self._history_count = len(self.ports.lookup.bits.history)
        for fields in (self.ports.lookup.bits.history, self.ports.training.bits.history):
            validate_folded_history_layout(signal_width(field.foldedHist) for field in fields)
        self._last_s0_lookup: TageLookup | None = None
        self.reset_driver = ResetDriver(dut)
        self.control_driver = ClockedWriteDriver(self.ports.control)
        lookup = self.ports.lookup.bits
        self.lookup_driver = AsyncSingleCycleDriver(
            PortBinding(
                dut.clock,
                Bundle(
                    s0_fire=lookup.s0_fire,
                    s1_fire=lookup.s1_fire,
                    s2_fire=lookup.s2_fire,
                    s3_fire=lookup.s3_fire,
                    start_pc=lookup.start_pc,
                    history=lookup.history,
                    main_btb=Bundle(s1_positions=lookup.main_btb.s1_positions),
                ),
                "tage.lookup_s0_s1",
            ),
            idle=lambda request: {
                "s0_fire": 0,
                "s1_fire": 0 if request is None else 1,
                "s2_fire": 0 if request is None else 1,
                "s3_fire": 0 if request is None else 1,
                "start_pc": 0 if request is None else request.pc,
                "history": folded_history_values(0 if request is None else request.history, self._history_count),
                "main_btb": {"s1_positions": self._main_btb(request)["s1_positions"]},
            },
            encoder=self._encode_lookup,
        )
        idle_context = self._main_btb(None)
        self.base_driver = AsyncSingleCycleDriver(
            PortBinding(
                dut.clock,
                Bundle(result=lookup.main_btb.result, baseConf=lookup.main_btb.baseConf),
                "tage.main_btb_s2",
            ),
            idle={
                "result": tuple({**entry, "valid": 0} for entry in idle_context["result"]),
                "baseConf": (0,) * self._main_btb_capacity,
            },
            encoder=lambda request: {
                key: self._main_btb(request)[key] for key in ("result", "baseConf")
            },
        )
        self._base_tasks: set[asyncio.Task[None]] = set()
        self.training_driver = PulseDriver(self.ports.training)
        self.monitor = CycleMonitor(self.ports.prediction, decoder=self._decode)
        self.reference = TageSemanticChecker()
        self.reference_monitor = TageSemanticMonitor(dut, self.ports)
        self.prediction_scoreboard = Scoreboard(
            "tage.prediction",
            compare=compare_prediction,
            expected=self.reference.response_expected,
        )
        self.feedback_scoreboard = Scoreboard('tage.feedback')
        self.write_scoreboard = Scoreboard('tage.highest_table_writes')
        self._write_monitor = None
        self._write_observation_active = False
        self._state_monitor = None
        self._selector_monitor = None
        self._state_observation_active = False
        self._shadow_monitor = None
        self._shadow_observation_active = False
        self._execution: Execution | None = None
        self._started = False

    async def start(self, execution: Execution) -> "TageAgent":
        self._execution = execution
        self.reference_monitor.start(execution, self.reference)
        await self.reset_driver.__aenter__()
        await self.control_driver.__aenter__()
        self.lookup_driver.start(execution)
        self.base_driver.start(execution)
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
        self._started = True
        await self.set_enabled(True)
        return self

    async def aclose(self) -> None:
        try:
            await self.prediction_scoreboard.aclose()
        finally:
            try:
                await self._close_base_tasks()
            finally:
                await self.reference_monitor.aclose()
                self.training_driver.close()
                await self.lookup_driver.aclose()
                await self.base_driver.aclose()
                self._selector_monitor = None
                self.control_driver.close()
                self.reset_driver.close()
                self._execution = None
                self._started = False
        self.reference.raise_unobserved_failure()

    async def reset(self, cycles: int = 3) -> int:
        await self._drain_base_tasks()
        self.lookup_driver.quiesce()
        self.base_driver.quiesce()
        self._last_s0_lookup = None
        await self.reset_driver.send(cycles)
        await self.set_enabled(True)
        return (await wait_reset_done(self.ports.status)).samples

    async def sample_selectors(self) -> tuple[int, ...]:
        """Read the eight ``useAltOnNa`` registers at a fresh edge.

        Read-only and quiescent: there is no write path, and the caller must
        only use it between accepted feedbacks.  Index ``2*table + altConf``.
        """

        if self._execution is None:
            raise RuntimeError('selector sampling requires a started TAGE agent')
        if self._selector_monitor is None:
            # A pure pull sampler: no background subscription, so the read
            # cannot queue up or miss an edge the caller waits for.
            self._selector_monitor = TageSelectorMonitor(self.dut)
        event = await ClockCycles(self.dut.clock, 1)
        return self._selector_monitor.sample_at(event).value

    async def set_enabled(self, enabled: bool) -> None:
        """Control lookup and training without changing individual requests."""

        await self._drain_base_tasks()
        self.lookup_driver.quiesce()
        self.base_driver.quiesce()
        self._last_s0_lookup = None
        await self.control_driver.send({"enable": int(enabled)})

    @asynccontextmanager
    async def observe_prediction_state(self):
        """Bounded scope: enrich the same snapshot, not a later native read."""
        if self._execution is None:
            raise RuntimeError('state observation requires a started TAGE agent')
        if self._state_observation_active:
            raise RuntimeError('TAGE prediction state observation is already active')
        await self.drain_predictions()
        if self._state_monitor is None:
            self._state_monitor = TagePredictionStateMonitor(self.dut, self.ports.prediction, self._decode)
        binding, decoder = self.monitor.binding, self.monitor.decoder
        self._state_observation_active = True
        self.monitor.binding, self.monitor.decoder = self._state_monitor.binding, self._state_monitor.decoder
        try:
            yield self
            await self.drain_predictions()
        finally:
            self.monitor.binding, self.monitor.decoder = binding, decoder
            self._state_observation_active = False

    @asynccontextmanager
    async def observe_writes(self):
        """Bounded passive observation, no clock/edge/native access in tests."""
        if self._execution is None:
            raise RuntimeError('write observation requires a started TAGE agent')
        if self._write_observation_active:
            raise RuntimeError('TAGE write observation is already active')
        if self._write_monitor is None:
            self._write_monitor = TageWriteActivityMonitor(self.dut)
        observations = []
        self._write_observation_active = True
        try:
            self._write_monitor.start(self._execution, observer=lambda observation: observations.append(observation)
                                      if any(port is not None for bank in observation.value['banks'] for port in bank) else None)
            yield observations
        finally:
            try:
                await self._write_monitor.aclose()
            finally:
                self._write_observation_active = False

    @asynccontextmanager
    async def observe_shadows(self):
        """Bounded passive snapshots of highest-table retained owners/depths."""
        if self._execution is None:
            raise RuntimeError('shadow observation requires a started TAGE agent')
        if self._shadow_observation_active:
            raise RuntimeError('TAGE shadow observation is already active')
        if self._shadow_monitor is None:
            self._shadow_monitor = TageShadowMonitor(self.dut)
        observations = []
        self._shadow_observation_active = True
        try:
            self._shadow_monitor.start(self._execution, observer=observations.append)
            yield observations
        finally:
            try:
                await self._shadow_monitor.aclose()
            finally:
                self._shadow_observation_active = False

    @asynccontextmanager
    async def observe_training(self):
        """Temporarily sample accepted feedback and its complete metadata."""

        if self._execution is None:
            raise RuntimeError("training observation requires a started TAGE agent")
        binding = self.ports.training
        observations = []
        monitor = CycleMonitor(
            PortBinding(
                self.dut.clock,
                Bundle(valid=binding.valid, ready=self.ports.status.bits.train_ready, bits=binding.bits),
                "tage.feedback_observation",
            ),
            decoder=_plain,
        )
        monitor.start(
            self._execution,
            observer=lambda observation: observations.append(observation)
            if observation.value["valid"] else None,
        )
        try:
            yield observations
        finally:
            await monitor.aclose()

    def _encode_lookup(self, request: TageLookup) -> dict[str, Any]:
        previous = self._last_s0_lookup or request
        self._last_s0_lookup = request
        return {
            "s0_fire": 1,
            "s1_fire": 1,
            "s2_fire": 1,
            "s3_fire": 1,
            "start_pc": request.pc,
            "history": folded_history_values(request.history, self._history_count),
            "main_btb": {"s1_positions": self._main_btb(previous)["s1_positions"]},
        }

    def _main_btb(self, request: TageLookup | None) -> dict[str, Any]:
        if request is None:
            return _main_btb(0, 0, capacity=self._main_btb_capacity)
        return _main_btb(
            request.position, request.base_taken, request.base_conf,
            request.branch_type, request.branches,
            capacity=self._main_btb_capacity,
        )

    def submit_predict(
        self,
        pc: int,
        position: int,
        base_taken: int,
        *,
        base_conf: int = 0,
        branch_type: int = 1,
        branches: Sequence[TageBaseBranch | None] | None = None,
        expected: Any = MISSING,
        history: int = 0,
    ) -> XTransfer[TageLookup, TagePrediction]:
        request = TageLookup(
            pc, position, base_taken, base_conf, branch_type,
            None if branches is None else tuple(branches),
            history,
        )
        self._main_btb(request)
        folded_history_values(history, self._history_count)
        transfer = self.prediction_scoreboard.submit(request, expected=expected)
        self._base_tasks.add(asyncio.create_task(self._drive_s2_base(transfer)))
        return transfer

    async def _drive_s2_base(self, transfer: XTransfer[TageLookup, TagePrediction]) -> None:
        await transfer.wait_processing()
        await ClockCycles(self.dut.clock, 1)
        await self.base_driver.send(transfer.request)

    async def _drain_base_tasks(self) -> None:
        while self._base_tasks:
            task = next(iter(self._base_tasks))
            try:
                await task
            finally:
                self._base_tasks.discard(task)

    async def _close_base_tasks(self) -> None:
        """Reclaim secondary tasks without reporting the same owned error twice.

        Scoreboard.aclose() has already handled its first failure, either by
        raising it or recognizing an observed failure. Other errors still raise.
        Normal driving continues to use _drain_base_tasks(), not this cleanup.
        """
        tasks = tuple(self._base_tasks)
        self._base_tasks.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        unexpected = None
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except BaseException as error:
                if error is not self.prediction_scoreboard.status.first_failure and unexpected is None:
                    unexpected = error
        if unexpected is not None:
            raise unexpected

    def submit_predict_branches(
        self,
        pc: int,
        branches: Sequence[TageBaseBranch | None],
        *,
        expected: Any = MISSING,
        history: int = 0,
    ) -> XTransfer[TageLookup, TagePrediction]:
        return self.submit_predict(pc, 0, 0, branches=branches, expected=expected, history=history)

    async def predict_branches(
        self,
        pc: int,
        branches: Sequence[TageBaseBranch | None],
        *,
        history: int = 0,
    ) -> TagePrediction:
        return await self.submit_predict_branches(pc, branches, history=history)

    async def drain_predictions(self):
        result = await self.prediction_scoreboard.drain(timeout_cycles=64)
        await self._drain_base_tasks()
        self.reference.raise_failure()
        return result

    async def predict(
        self,
        pc: int,
        position: int,
        base_taken: int,
        *,
        base_conf: int = 0,
        branch_type: int = 1,
        history: int = 0,
    ) -> TagePrediction:
        return await self.submit_predict(
            pc, position, base_taken, base_conf=base_conf, branch_type=branch_type, history=history
        )

    def encode_training(self, transaction: TageTraining) -> dict[str, Any]:
        """Retain the single-branch API over the full feedback-vector encoding."""

        return self.encode_batch_training(
            TageBatchTraining(
                transaction.pc,
                (TageBranchFeedback(
                    position=transaction.position,
                    actual_taken=transaction.actual_taken,
                    base_taken=transaction.base_taken,
                    meta=transaction.meta,
                    mispredict=transaction.mispredict,
                    base_counter_value=transaction.base_counter_value,
                    branch_type=transaction.branch_type,
                    mbtb_hit=transaction.mbtb_hit,
                ),), transaction.history,
            )
        )

    def encode_batch_training(self, transaction: TageBatchTraining) -> dict[str, Any]:
        branch_count = len(self.ports.training.bits.branches)
        if not 1 <= len(transaction.branches) <= branch_count:
            raise ValueError(f"TAGE feedback requires 1 to {branch_count} branches")
        active = tuple(
            branch for branch in transaction.branches
            if branch is not None and branch.valid
        )
        matched = tuple(branch for branch in active if branch.mbtb_hit)
        meta_count = len(self.ports.training.bits.tage_meta)
        mbtb_shape = tuple(len(bank) for bank in self.ports.training.bits.mbtb_meta)
        if not active:
            raise ValueError("TAGE feedback requires at least one valid branch")
        if len(matched) > meta_count:
            raise ValueError(f"TAGE feedback permits at most {meta_count} MainBTB hits")
        if sum(mbtb_shape) != meta_count:
            raise ValueError("TAGE metadata and MainBTB metadata sizes differ")
        if len({branch.position for branch in active}) != len(active):
            raise ValueError("TAGE feedback positions must be distinct")
        if sum(bool(branch.mispredict) for branch in active) > 1:
            raise ValueError("TAGE feedback permits at most one mispredicted branch")

        # The RTL associates a resolved branch with a prediction-meta slot via
        # MainBTB rawHit/position, not via its index in the resolve vector.
        # Assign one distinct MBTB entry per matched branch in flattened order.
        # A valid feedback branch without a MainBTB hit must remain unmatched.
        mbtb_entries = []
        tage_entries = [active[0].meta] * meta_count
        for index in range(meta_count):
            if index < len(matched):
                branch = matched[index]
                counter = _base_counter(branch.base_taken, branch.base_counter_value)
                mbtb_entries.append({
                    "rawHit": 1,
                    "position": branch.position,
                    "attribute": {"branchType": branch.branch_type, "rasAction": 0},
                    "counter_value": counter,
                })
                tage_entries[index] = branch.meta
            else:
                mbtb_entries.append({
                    "rawHit": 0,
                    "position": 0,
                    "attribute": {"branchType": 0, "rasAction": 0},
                    "counter_value": 0,
                })
        mbtb_meta = []
        offset = 0
        for size in mbtb_shape:
            mbtb_meta.append(tuple(mbtb_entries[offset:offset + size]))
            offset += size
        branches = transaction.branches + (None,) * (branch_count - len(transaction.branches))
        return {
            "start_pc": transaction.pc,
            "history": folded_history_values(transaction.history, len(PHR_FOLD_LAYOUT)),
            "mbtb_meta": tuple(mbtb_meta),
            "tage_meta": tuple(tage_entries),
            "branches": tuple(_encode_branch_feedback(branch) for branch in branches),
        }

    async def train(self, transaction: TageTraining) -> None:
        await self._send_training(self.encode_training(transaction))

    async def train_batch(self, transaction: TageBatchTraining) -> None:
        await self._send_training(self.encode_batch_training(transaction))

    async def train_checked(self, transaction: TageBatchTraining, observations) -> None:
        """Drive one beat and independently check its actual placement/metadata.

        The caller supplies the list yielded by observe_training(). Expected
        content is frozen before driving, without calling either encoder.
        """
        expected = expected_tage_feedback(
            transaction, branch_count=len(self.ports.training.bits.branches),
        )
        first = len(observations)
        await self.train_batch(transaction)
        frames = observations[first:]
        actual = {'beats': len(frames)}
        if len(frames) == 1:
            actual['frame'] = observed_tage_feedback(frames[0].value)
        self.feedback_scoreboard.check(
            expected={'beats': 1, 'frame': expected}, actual=actual,
            context=CheckContext(
                scoreboard='tage.feedback', mode=ScoreboardMode.DIRECT,
                sequence_id=first + 1, request=transaction,
                accepted_event=frames[0].event if len(frames) == 1 else None,
                observed_event=frames[-1].event if frames else None,
            ),
        )

    async def train_with_writes_checked(self, transaction, feedback, writes, *, expected_activity):
        """Compare input and the complete same-event write activity independently."""
        expected = deepcopy(expected_activity)
        first_feedback, first_write = len(feedback), len(writes)
        await self.train_checked(transaction, feedback)
        accepted = feedback[first_feedback].event
        frames = writes[first_write:]
        actual = {'beats': len(frames)}
        if len(frames) == 1:
            actual.update(banks=frames[0].value['banks'], latency_ticks=frames[0].event.tick-accepted.tick)
        self.write_scoreboard.check(expected=expected, actual=actual, context=CheckContext(
            scoreboard='tage.highest_table_writes', mode=ScoreboardMode.DIRECT,
            sequence_id=first_feedback+1, request=transaction, accepted_event=accepted,
            observed_event=frames[0].event if frames else None,
        ))

    async def train_batches_with_writes_checked(self, transactions, feedback, writes,
                                               *, expected_activity, sequential=False):
        """Check burst input, cadence and all write events without exposing scheduling.

        Expected input frames are independent of encode_batch_training and
        frozen before driving. Sequential mode drains each transaction; burst
        mode retains adjacent acceptance. Both use the same comparison path.
        """
        transactions = tuple(transactions)
        if not transactions:
            raise ValueError('checked TAGE feedback burst must not be empty')
        expected_input = [expected_tage_feedback(transaction,
                          branch_count=len(self.ports.training.bits.branches))
                          for transaction in transactions]
        expected_writes = deepcopy(expected_activity)
        first_feedback, first_write = len(feedback), len(writes)
        if sequential:
            for transaction in transactions:
                await self.train_batch(transaction)
        else:
            await self.train_batches(transactions)
        accepted, frames = feedback[first_feedback:], writes[first_write:]
        intervals = tuple(after.event.tick-before.event.tick
                          for before, after in zip(accepted, accepted[1:]))
        context = CheckContext(
            scoreboard='tage.feedback', mode=ScoreboardMode.DIRECT,
            sequence_id=first_feedback+1, request=transactions,
            accepted_event=accepted[0].event if accepted else None,
            observed_event=frames[-1].event if frames else None,
        )
        self.feedback_scoreboard.check(
            expected={'beats':len(transactions), 'frames':expected_input, 'cadence_ok':True},
            actual={'beats':len(accepted),
                    'frames':[observed_tage_feedback(frame.value) for frame in accepted],
                    'cadence_ok':all(interval > 8 if sequential else interval == 2
                                     for interval in intervals)}, context=context)
        self.write_scoreboard.check(expected=expected_writes, actual={
            'beats':len(frames), 'banks':tuple(frame.value['banks'] for frame in frames),
            'latency_ticks':tuple(frame.event.tick-accepted[i].event.tick if i < len(accepted) else None
                                  for i,frame in enumerate(frames)),
        }, context=CheckContext(
            scoreboard='tage.highest_table_writes', mode=ScoreboardMode.DIRECT,
            sequence_id=first_feedback+1, request=transactions,
            accepted_event=accepted[0].event if accepted else None,
            observed_event=frames[-1].event if frames else None,
        ))

    async def train_batches(self, transactions: Sequence[TageBatchTraining]) -> None:
        """Send FTQ feedback on adjacent cycles after quiescing prediction reads."""

        if not transactions:
            raise ValueError("TAGE feedback burst must not be empty")
        await self._drain_base_tasks()
        self.lookup_driver.quiesce()
        self.base_driver.quiesce()
        self._last_s0_lookup = None
        await self.training_driver.send_many(
            tuple(self.encode_batch_training(transaction) for transaction in transactions)
        )
        await self.training_activity.wait_idle('pipeline', 'writes')
        self.reference.raise_failure()

    async def train_batches_with_read_pressure(self, transactions, read_request: TageLookup, *, expected=MISSING):
        """Keep normal pipelined predictions active while accepting feedback.

        Correct provider-only feedback can use captured metadata without SRAM
        rereads. Same-bank prediction reads then defer entry-buffer drain.
        This operation checks the read stream through the existing asynchronous
        prediction Scoreboard and returns its completed transfers. The caller
        independently checks training readiness. Feedback requiring a same-bank
        SRAM reread is rejected before driving this provider-only operation.
        """
        transactions = tuple(transactions)
        if not transactions:
            raise ValueError('TAGE feedback under read pressure must not be empty')
        if not isinstance(read_request, TageLookup):
            raise TypeError('TAGE read pressure requires a TageLookup request')
        # Validate the entire operation before quiescing or submitting anything.
        encoded = tuple(self.encode_batch_training(tx) for tx in transactions)
        self._main_btb(read_request)
        for transaction in transactions:
            if transaction.pc & 3 != read_request.pc & 3:
                raise ValueError('TAGE read pressure requires same-bank feedback')
            for branch in transaction.branches:
                if branch is not None and branch.valid and branch.branch_type == 1 and branch.mbtb_hit:
                    if branch.mispredict or (not branch.meta['useProvider'] and branch.meta['hasAlt']):
                        raise ValueError('TAGE feedback under read pressure must not require SRAM rereads')
        await self.drain_predictions()
        transfers = []

        async def read_stream():
            while True:
                transfers.append(self.submit_predict(read_request.pc, read_request.position, read_request.base_taken,
                    base_conf=read_request.base_conf, branch_type=read_request.branch_type,
                    branches=read_request.branches, expected=expected, history=read_request.history))
                await ClockCycles(self.dut.clock, 1)  # Throughput, not a settling delay.

        reader = asyncio.create_task(read_stream())
        try:
            try:
                await self.training_activity.wait_active('reads')
                await self.training_driver.send_many(encoded)
                await self.training_activity.wait_idle('pipeline')
            finally:
                reader.cancel()
                with suppress(asyncio.CancelledError):
                    await reader
            await self.drain_predictions()
        except BaseException:
            for transfer in transfers:
                transfer.cancel()
            raise
        finally:
            self.lookup_driver.quiesce()
            self.base_driver.quiesce()
            self._last_s0_lookup = None
        await self.training_activity.wait_idle('pipeline', 'writes')
        self.reference.raise_failure()
        return tuple(transfers)

    async def _send_training(self, encoded: dict[str, Any]) -> None:
        await self._drain_base_tasks()
        self.lookup_driver.quiesce()
        self.base_driver.quiesce()
        self._last_s0_lookup = None
        await self.training_driver.send(encoded)
        await self.training_activity.wait_idle('pipeline', 'writes')
        self.reference.raise_failure()

    _decode = staticmethod(_decode)
