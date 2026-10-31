"""Normal predictions and feedback; existing agents own every clock detail."""
from suites.frontend.bpu.models.configuration import *
from suites.frontend.bpu.models.configuration import MAIN_WAYS as WAYS
from copy import deepcopy

from suites.frontend.bpu.mbtb.checker.full_capacity_learning import FullCapacityChecks
from suites.frontend.bpu.mbtb.transaction.types import MbtbBatchTraining, MbtbBranchFeedback


def planned_payload(transaction):
    # Whole-chip DCE removed the VictimBTB sideband from the training port;
    # the training snapshot therefore owns exactly the four MainBTB ways.
    sources = tuple(tuple(
        (int(s['rawHit']), s['position'], s['attribute']['branchType'],
         s['attribute']['rasAction'], s['counter_value']) for s in row[:WAYS])
        for row in transaction.meta_entries)
    branches = tuple((b.position, b.target, b.taken, b.branch_type, b.ras_action, b.mispredict)
                     for b in transaction.branches)
    return (transaction.pc, (transaction.pc // ALIGN_HALFWORDS + 1) * ALIGN_HALFWORDS), sources, branches


def observed_payload(feedback):
    sources = tuple(tuple((int(s.hit), s.position, s.kind, s.action, s.counter) for s in row[:WAYS])
                    for row in feedback.sources)
    branches = tuple((b.position, b.target, int(b.taken), b.kind, b.action, int(b.mispredict))
                     for b in feedback.branches)
    return feedback.pcs, sources, branches


class FullCapacityEnv:
    def __init__(self, agent, mode, order, coverage, *, position_relation='same-position'):
        self.agent, self.mode = agent, mode
        self.checks = FullCapacityChecks(mode, order, coverage, position_relation=position_relation)
        self.program = self.checks.program
        self.phase = 'preparation'
        self.last_teaching = None

    async def predict(self, owner):
        transfer = self.agent.submit_predict(self.program.branches[owner].pc)
        prediction = await transfer
        self.agent.reference.raise_failure()
        return transfer, prediction

    async def read(self, stage, owners, *, after=None):
        for owner in owners:
            transfer, prediction = await self.predict(owner)
            self.checks.response(stage, owner, transfer, prediction, after=after)

    def feedback(self, owner, source, *, taken=1, allocate=True):
        r = self.program.branches[owner]
        return MbtbBatchTraining(r.pc, deepcopy(source.meta_entries), (
            MbtbBranchFeedback(r.target, taken, r.position, r.kind, r.action, int(allocate)),))

    async def teach(self, owner, *, taken=1, allocate=True, source_stage=None):
        transfer, source = await self.predict(owner)
        if source_stage is not None:
            self.checks.response(source_stage, owner, transfer, source)
        tx = self.feedback(owner, source, taken=taken, allocate=allocate)
        before = self.agent.reference.accepted_feedback[-1][0] if self.agent.reference.accepted_feedback else -1
        await self.agent.train_batch(tx)
        receipts = tuple((tick, observed_payload(fb)) for tick, fb in self.agent.reference.accepted_feedback if tick > before)
        self.checks.check(1, len(receipts), 'one teaching feedback actually accepted')
        self.checks.check(planned_payload(tx), receipts[0][1], 'complete teaching feedback uses its original source')
        self.last_teaching = dict(owner=owner, source_accepted_tick=transfer.accepted_event.tick,
            source_completed_tick=transfer.completed_event.tick, accepted=receipts)
        return receipts[0][0]

    async def prepare(self):
        await self.agent.reset()
        # Distinct old positions prevent cold allocation from legitimately
        # resolving an earlier branch in the same public branch vector.
        for owner in ('old-a', 'old-b'):
            await self.teach(owner)
        for _ in range(2):
            await self.teach('old-a', taken=0, allocate=False)
        await self.teach('old-b', allocate=False)
        for owner in ('old-c', 'old-d', 'neighbor-a', 'neighbor-b', 'neighbor-c', 'neighbor-d'):
            await self.teach(owner)
        await self.teach('neighbor-a', allocate=False)
        await self.read('prepared', ('old-a', 'old-b', 'old-c', 'old-d', 'neighbor-a', 'neighbor-b', 'neighbor-c', 'neighbor-d'))
        self.checks.reach('full-distinct-old-residents',
            residents=self.program.stages['prepared'], victims=self.program.victims['prepared'],
            consumers=self.checks.consumer_witness('prepared', ('old-a', 'old-b', 'old-c', 'old-d', 'neighbor-a', 'neighbor-b', 'neighbor-c', 'neighbor-d')))

    async def learn_pair(self):
        self.phase = 'capture two real independent cold sources'
        transfers = tuple(self.agent.submit_predict(self.program.branches[owner].pc)
                          for owner in self.program.sequence)
        await self.agent.drain_predictions()
        predictions = tuple([await transfer for transfer in transfers])
        self.checks.sources(transfers, predictions)
        transactions = tuple(self.feedback(owner, source)
            for owner, source in zip(self.program.sequence, predictions, strict=True))
        self.phase = 'accept both original feedbacks'
        before = self.agent.reference.accepted_feedback[-1][0]
        if self.mode == 'adjacent':
            await self.agent.train_burst(transactions)
        else:
            for transaction in transactions:
                await self.agent.train_batch(transaction)
        receipts = tuple((tick, observed_payload(fb)) for tick, fb in self.agent.reference.accepted_feedback
                         if tick > before)
        self.checks.admissions(receipts, tuple(planned_payload(tx) for tx in transactions))
        self.phase = 'fresh complete new-branch consumers'
        await self.read('pair', self.program.sequence, after=receipts[-1][0])
        self.checks.reach('two-new-identities-and-directions',
                          consumers={o: self.checks.consumers['pair', o] for o in self.program.sequence})
        await self.read('pair', ('old-a', 'old-b', 'old-c', 'old-d'), after=receipts[-1][0])
        self.checks.reach('old-residents-retired', consumers=self.checks.consumer_witness('pair', ('old-a', 'old-b')))
        await self.read('pair', ('neighbor-a', 'neighbor-b', 'neighbor-c', 'neighbor-d'), after=receipts[-1][0])
        self.checks.reach('independent-window-content',
                          consumers=self.checks.consumer_witness('pair', ('neighbor-a', 'neighbor-b')))

    async def compete(self):
        self.phase = 'neighbor competition before any further target age update'
        tick = await self.teach('neighbor-probe', source_stage='pair')
        owners = (*self.program.sequence, 'old-c', 'old-d', 'neighbor-a', 'neighbor-b', 'neighbor-c', 'neighbor-d', 'neighbor-probe')
        await self.read('neighbor-probe', owners, after=tick)
        self.checks.reach('independent-next-victim', evicted='neighbor-b', kept='neighbor-a',
            feedback=self.last_teaching, consumers=self.checks.consumer_witness('neighbor-probe', owners))
        self.phase = 'qualified neighbor recency feedback cannot touch target age'
        tick = await self.teach('neighbor-a', allocate=False, source_stage='neighbor-probe')
        await self.read('neighbor-touch', owners, after=tick)
        neighbor_touch = dict(feedback=self.last_teaching,
                             consumers=self.checks.consumer_witness('neighbor-touch', owners))
        self.phase = 'target competition after discriminating qualified neighbor touch'
        tick = await self.teach('target-probe', source_stage='neighbor-touch')
        owners = (*self.program.sequence, 'old-c', 'old-d', 'target-probe', 'neighbor-a', 'neighbor-b', 'neighbor-c', 'neighbor-d', 'neighbor-probe')
        await self.read('target-probe', owners, after=tick)
        self.checks.reach('target-next-victim', evicted='old-c', kept='old-d',
            feedback=self.last_teaching, independent_touch=neighbor_touch,
            consumers=self.checks.consumer_witness('target-probe', owners))

    def annotate_failure(self, error):
        error.add_note('MainBTB full-capacity semantic program: ' + repr(dict(phase=self.phase,
            mode=self.mode, order=self.program.order, accepted=self.checks.accepted,
            independent_program=self.program.state(), reached=sorted(self.checks.completed))))
