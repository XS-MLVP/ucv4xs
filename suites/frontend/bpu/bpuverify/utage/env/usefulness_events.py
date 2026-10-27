"""Normal sources, actual feedback receipts and complete read-only observation."""
from contextlib import asynccontextmanager
from copy import deepcopy

from bpuverify.utage.checker.checking import UtageUsefulChecker
from bpuverify.utage.checker.usefulness_events import UsefulnessChecks
from bpuverify.utage.model.semantic import Context, indices
from bpuverify.utage.model.usefulness_events import PC, POSITION, HISTORY, NEIGHBOR_HISTORY, SHORT_CONSUMER_HISTORY
from bpuverify.utage.transaction.types import UtageTraining


class UsefulnessEnv:
    def __init__(self, agent, program, coverage, checker):
        self.agent, self.program, self.checker = agent, program, checker
        self.checks = UsefulnessChecks(program, coverage)
        self.sources, self.frozen = [], []

    async def read(self, history, base, *, expected=None):
        prediction = await self.agent.predict(PC, POSITION, base, folded_history=history)
        self.sources.append(prediction)
        self.frozen.append(deepcopy(prediction.meta))
        if expected is not None:
            self.checks.provider(prediction, expected, point='fresh owned provider, direction and full counter')
        return prediction

    async def feedback(self, source, actual, *, count=1, phase, mode='serial', credit=False):
        transactions = tuple(UtageTraining(PC, POSITION, actual, deepcopy(source.meta),
            mispredict=int(source.taken != actual)) for _ in range(count))
        self.checker.plan(transactions, phase=phase)
        before = len(self.checker.accepted_feedback)
        try:
            if mode == 'adjacent':
                await self.agent.train_many(transactions)
            else:
                for transaction in transactions:
                    await self.agent.train(transaction)
        finally:
            if credit:
                actual_receipts = self.checker.accepted_feedback[before:]
                # A failed/partial offer cannot qualify a complete two-feedback
                # event, but an actual accepted event keeps reached on mismatch.
                if len(actual_receipts) == count:
                    self.checks.admissions(actual_receipts, tuple(self.checker._payload(t) for t in transactions),
                                           cycle_ticks=self.checker.reference.cycle_ticks)
        self.checker.finish_phase()

    async def seed(self, history, *, credit=False):
        cold = await self.read(history, 1)
        self.checks.check(0, cold.hit, 'normal cold context before learning')
        await self.feedback(cold, 0, phase='new short identity', credit=credit and self.program.table == 0)
        short = await self.read(history, 1)
        slot = short.meta['abtbResult'][0]
        self.checks.check((1, 0, 3, 0), (short.hit, slot['tableId'], slot['takenCtr_value'], short.taken),
                          'normally allocated short source')
        if self.program.table == 0:
            return short
        await self.feedback(short, 1, phase='new long identity', credit=credit)
        return await self.read(history, 0, expected=self.program.initial)

    def useful(self, expected, history=HISTORY):
        index = indices(PC, Context.from_recent(history))[self.program.table]
        self.agent.check_useful(self.program.table, index, expected)
        self.checker.finish_phase()

    @property
    def consumer_history(self):
        return SHORT_CONSUMER_HISTORY if self.program.table == 0 else HISTORY

    @property
    def source_history(self):
        # Wrong short-provider feedback can allocate the long table. Keep the
        # independent long-history alias available as a genuine short consumer.
        if self.program.table == 0 and self.program.actual != self.program.source.taken:
            return HISTORY
        return self.consumer_history

    async def consumers(self, expected):
        target = await self.read(self.consumer_history, expected.taken)
        neighbor = await self.read(NEIGHBOR_HISTORY, self.program.initial.taken)
        self.useful(expected.useful)
        self.useful(self.program.initial.useful, NEIGHBOR_HISTORY)
        self.checks.consumers(target, neighbor)

    def finish(self):
        self.checker.finish_phase()
        self.agent.reference.raise_failure()
        self.checks.finish(tuple(self.frozen), tuple(source.meta for source in self.sources))


@asynccontextmanager
async def usefulness_env(agent, program, coverage):
    await agent.reset()
    checker = UtageUsefulChecker(mode=program.mode, scope=program.state())
    async with agent.observe_useful(checker):
        yield UsefulnessEnv(agent, program, coverage, checker)
