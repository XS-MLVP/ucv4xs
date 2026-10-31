"""Normal learning sources and concurrent existing drivers; no raw I/O."""
from copy import deepcopy
from dataclasses import replace

from suites.frontend.bpu.utage.model.read_ownership import FeedbackLedger
from suites.frontend.bpu.utage.model.source_ownership import POSITION
from suites.frontend.bpu.utage.transaction.types import UtageTraining


class ReadOwnershipEnv:
    # One query for each named interval in the existing registered feedback
    # protocol. A burst keeps reads active through application, rather than
    # waiting a magic settling delay in the testcase.
    LEARNING_INTERVALS = ('public-feedback', 'registered-feedback',
                          'learning-effect', 'new-read')

    def __init__(self, agent, program, checks):
        self.agent, self.program, self.checks = agent, program, checks
        self.originals = []
        self.ledger = FeedbackLedger()
        self.expected_feedback = []
        self.transfers = ()
        self.source_tokens = {}

    def remember(self, actual):
        self.originals.append((actual, deepcopy(actual.meta)))
        return actual

    async def read(self, profile, base):
        transfer = self.agent.submit_predict(profile.pc, POSITION, base, folded_history=profile.history)
        actual = self.remember(await transfer)
        self.agent.reference.raise_failure()
        self.source_tokens[id(actual)] = transfer.sequence_id
        self.checks.profile(profile, actual, base)
        return actual

    def feedback(self, profile, source):
        token = self.source_tokens[id(source)]
        self.ledger.capture(token, profile, source.meta)
        _, frozen = self.ledger.consume(token)
        transaction = UtageTraining(profile.pc, POSITION, profile.taken, frozen,
                                    mispredict=int(not source.hit))
        self.expected_feedback.append(self.agent.encode_training(transaction))
        return transaction

    async def prepare(self):
        p = self.program
        for profile in (p.original, replace(p.learning, counter=4)):
            base = 1 - profile.taken
            source = await self.read(replace(profile, counter=None), base)
            await self.agent.train(self.feedback(profile, source))
            await self.read(profile, base)
        current = replace(p.learning, counter=4)
        for result in p.preparation[2:]:
            source = await self.read(current, 0)
            await self.agent.train(self.feedback(current, source))
            await self.read(result, 0)
            current = result
        await self.read(p.original, 1)
        await self.read(p.neighbor, 0)
        self.checks.reached('distinct-original-records')
        self.checks.end('distinct-original-records')

    async def overlap(self):
        p = self.program
        source = await self.read(p.learning, 0)
        transaction = self.feedback(p.learning, source)
        self.transfers = tuple(self.agent.submit_predict(p.learning.pc, POSITION, 0,
            folded_history=p.learning.history, index_pc=p.original.pc, index_history=p.original.history)
            for _ in self.LEARNING_INTERVALS)
        await self.agent.train(transaction)
        await self.agent.drain_predictions()
        return tuple([self.remember(await transfer) for transfer in self.transfers])

    async def consumers(self):
        for profile, base in ((self.program.original, 1), (self.program.learning, 0),
                              (self.program.neighbor, 0)):
            await self.read(profile, base)
        self.checks.reached('fresh-records-preserved')
        self.checks.end('fresh-records-preserved')
