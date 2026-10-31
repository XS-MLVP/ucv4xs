"""Public query/feedback batches and read-only full-state observation."""
from contextlib import asynccontextmanager
from collections import deque
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256

from suites.frontend.bpu.utage.checker.checking import UtageUsefulChecker
from suites.frontend.bpu.utage.checker.working_set import WorkingSetChecks
from suites.frontend.bpu.utage.model.usefulness_events import ProtectionState
from suites.frontend.bpu.utage.model.working_set import PC, POSITION, SHORT_POSITION
from suites.frontend.bpu.utage.transaction.types import UtageTraining


class WorkingSetEnv:
    def __init__(self, agent, program, coverage, monitor):
        self.agent, self.program, self.monitor = agent, program, monitor
        self.checks = WorkingSetChecks(program, coverage)

    async def read(self, histories, base, *, position=POSITION):
        histories = tuple(histories)
        transfers, predictions, pending = [], [], deque()
        capacity = self.agent.prediction_scoreboard.capacity
        for history in histories:
            # Respect the framework's declared outstanding capacity. A sliding
            # window keeps the pipeline occupied without a per-batch drain or
            # an arbitrarily enlarged queue/deadline.
            if len(pending) == capacity:
                predictions.append(await pending.popleft())
            transfer = self.agent.submit_predict(PC, position, base, folded_history=history)
            transfers.append(transfer)
            pending.append(transfer)
        # A response timeout bounds each processing transfer, not the total
        # length of a legal workload. Await owned transfers before final drain
        # instead of imposing the adapter's64-cycle whole-batch deadline.
        while pending:
            predictions.append(await pending.popleft())
        await self.agent.drain_predictions()
        return histories, tuple(transfers), tuple(predictions)

    async def send(self, transactions, phase, *, owners=None):
        self.monitor.plan(transactions, phase=phase)
        before = len(self.monitor.accepted_feedback)
        try:
            if self.program.mode == 'adjacent':
                await self.agent.train_many(transactions)
            else:
                for transaction in transactions:
                    await self.agent.train(transaction)
        finally:
            receipts = self.monitor.accepted_feedback[before:]
            if owners is not None and len(receipts) == len(transactions):
                self.checks.admissions(phase, owners, receipts,
                    tuple(self.monitor._payload(t) for t in transactions), cycle_ticks=self.monitor.reference.cycle_ticks)
        self.monitor.finish_phase()

    async def prepare(self):
        histories, transfers, predictions = await self.read(self.program.short_histories, 0, position=SHORT_POSITION)
        self.checks.responses(histories, transfers, predictions, 0, {}, table=0, position=SHORT_POSITION)
        transactions = tuple(UtageTraining(PC, SHORT_POSITION, 1, deepcopy(source.meta), mispredict=1)
                             for source in predictions)
        await self.send(transactions, 'normal short-history prerequisites')
        histories, transfers, predictions = await self.read(self.program.short_histories, 0, position=SHORT_POSITION)
        self.checks.responses(histories, transfers, predictions, 0,
            {history: ProtectionState(4, 1) for history in histories}, table=0, position=SHORT_POSITION)
        self.checks.check(self.checks.reference.values(), tuple(self.monitor._actual),
                          'normal short identities precede all long admissions')

    async def phase(self, phase):
        histories, transfers, predictions = await self.read(self.program.order(phase), self.program.base(phase))
        owners = self.checks.capture(phase, transfers, predictions)
        transactions = tuple(UtageTraining(PC, POSITION, self.program.actual(phase), deepcopy(source.meta),
            mispredict=int((source.meta['abtbResult'][0]['predTaken'] if source.hit else self.program.base(phase))
                           != self.program.actual(phase))) for source in predictions)
        await self.send(transactions, phase, owners=owners)
        confirmation = self.monitor.reference.last_tick
        consumers = await self.read(self.program.histories, 0)
        await self.short_consumers()
        self.checks.verified_phase(phase, owners, tuple(self.monitor._actual), consumers,
                                   confirmation_tick=confirmation)

    async def short_consumers(self):
        histories, transfers, predictions = await self.read(self.program.short_histories, 0, position=SHORT_POSITION)
        self.checks.responses(histories, transfers, predictions, 0,
            {history: ProtectionState(4, 1) for history in histories}, table=0, position=SHORT_POSITION)

    async def finish(self):
        confirmation = self.monitor.reference.last_tick
        # No reset or artificial delay: other logical identities perform real
        # queries between the last learning and the delayed full revisit.
        await self.short_consumers()
        consumers = await self.read(self.program.histories, 0)
        self.monitor.finish_phase()
        self.agent.reference.raise_failure()
        self.checks.finish(tuple(self.monitor._actual), consumers, confirmation_tick=confirmation)


@asynccontextmanager
async def working_set_env(agent, program, coverage):
    await agent.reset()
    monitor = UtageUsefulChecker(mode=program.mode, scope=dict(program=asdict(program)))
    env = WorkingSetEnv(agent, program, coverage, monitor)
    try:
        async with agent.observe_useful(monitor):
            yield env
    except BaseException as error:
        coverage.evidence = dict(env.checks.summary(), status='FAIL',
            first_error_type=type(error).__name__, first_error=str(error))
        raise
    else:
        coverage.evidence = dict(env.checks.summary(), status='PASS')
    finally:
        if coverage.evidence is not None:
            coverage.evidence.update(actual_public_feedback=monitor.accepted_count,
                actual_all_cell_comparisons=monitor.cell_comparisons,
                protection_reference_pending=monitor.reference.pending,
                actual_protection_sha256=sha256(bytes(monitor._actual)).hexdigest())
