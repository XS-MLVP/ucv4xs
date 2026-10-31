"""Normal driver transactions and owned responses; no pin or edge handling."""
from suites.frontend.bpu.utage.model.aging_learning import POSITION


class AgingLearningEnv:
    def __init__(self, agent, checks):
        self.agent, self.checks = agent, checks

    async def _read(self, expected):
        context = expected.context
        transfer = self.agent.submit_predict(context.pc, POSITION, expected.base,
                                              folded_history=context.history)
        prediction = await transfer
        self.agent.reference.raise_failure()
        self.checks.raise_failure()
        return transfer, prediction

    async def source(self, expected):
        transfer, prediction = await self._read(expected)
        return self.checks.remember(transfer, prediction, expected)

    async def consumer(self, expected):
        _, prediction = await self._read(expected)
        self.checks.consumer(expected, prediction)

    async def send(self, learning, source_id, *, phase):
        await self.send_many(((learning, source_id, phase),))

    async def send_many(self, entries):
        transactions = tuple((source, phase, self.checks.transaction(source, learning))
                             for learning, source, phase in entries)
        self.checks.plan(transactions)
        await self.agent.train_many(tuple(transaction for _, _, transaction in transactions))
        self.agent.reference.raise_failure()
        self.checks.raise_failure()

    async def learn(self, learning, *, phase):
        source = await self.source(learning.source)
        await self.send(learning, source, phase=phase)
