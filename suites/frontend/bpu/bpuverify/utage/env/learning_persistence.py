"""Real branch histories and original feedback; no artificial settling delay."""
from collections import deque
from copy import deepcopy
from hashlib import sha256
import json

from toffee import TransferState
from bpuverify.utage.checker.learning_persistence import PersistenceChecks
from bpuverify.utage.checker.checking import UtageUsefulChecker
from bpuverify.utage.checker.source_ownership import actual_fields
from bpuverify.utage.model.usefulness_events import ProtectionState
from bpuverify.utage.model.working_set import expected
from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.model.persistence import PersistenceLedger, Version
from bpuverify.utage.monitor.learning_persistence import Monitor
from bpuverify.utage.model.learning_persistence import PC, POSITION, SHORT_POSITION
from bpuverify.utage.bundle.values import _plain


class Environment:
    def __init__(self, agent, program, coverage, evidence):
        self.agent, self.program, self.coverage, self.evidence = agent, program, coverage, evidence
        self.ledger = PersistenceLedger()
        self.monitor = Monitor(agent, program, self.ledger)
        self.checker = PersistenceChecks(program, self.ledger)
        self.board = self.checker.board
        self.originals, self.phases = [], []
        self.cycle_ticks = None

    def check(self, wanted, actual, point):
        self.checker.check(wanted, actual, point, phases=self.phases)

    async def queries(self, histories, *, table, counter=None, phase=None):
        position = SHORT_POSITION if table == 0 else POSITION
        transfers, results, pending = [], [], deque()
        for history in histories:
            if len(pending) == self.agent.prediction_scoreboard.capacity:
                results.append(await pending.popleft())
            request = self.program.lookup(history, table, phase=phase)
            transfer = self.agent.submit_predict(request.pc, request.position, request.base_taken,
                folded_history=request.folded_history, index_pc=request.index_pc, index_history=request.index_history)
            transfers.append(transfer); pending.append(transfer)
        while pending:
            results.append(await pending.popleft())
        await self.agent.drain_predictions()
        self.monitor.check()
        self.check(True, all(t.state is TransferState.COMPLETED for t in transfers), 'actual completed original queries')
        self.check(True, all(a.accepted_event.tick < b.accepted_event.tick < a.completed_event.tick
            for a, b in zip(transfers, transfers[1:])), 'real query pipeline overlap')
        if self.cycle_ticks is None:
            self.cycle_ticks = transfers[1].accepted_event.tick - transfers[0].accepted_event.tick
        for history, source in zip(histories, results, strict=True):
            wanted = self.program.expected(history, table, counter, phase=phase)
            self.check(wanted, actual_fields(source, wanted), 'complete independent original prediction')
            self.originals.append((source, deepcopy(source.meta)))
        return tuple(transfers), tuple(results)

    async def learn(self, phase, *, table, before_counter):
        p = self.program
        histories = p.order(phase)
        transfers, sources = await self.queries(histories, table=table, counter=before_counter, phase=phase)
        transactions, owners = [], []
        for history, transfer, source in zip(histories, transfers, sources, strict=True):
            version = Version(transfer.accepted_event.tick, p.identity(history, table), p.counter(phase), phase)
            tx = UtageTraining(PC, SHORT_POSITION if table == 0 else POSITION, p.actual(phase), deepcopy(source.meta),
                               mispredict=int(not source.hit))
            self.ledger.source(version, UtageUsefulChecker._payload(tx))
            transactions.append(tx); owners.append(version.owner)
        start = len(self.ledger.feedback)
        if p.mode == 'serial':
            for transaction in transactions:
                await self.agent.train(transaction)
        else:
            await self.agent.train_many(tuple(transactions))
        self.monitor.check()
        self.ledger.finish_phase(owners, persistent=False)
        receipts = self.ledger.feedback[start:]
        self.check(len(owners), len(receipts), 'every fresh original is accepted exactly once')
        self.check(True, all((b['tick'] - a['tick'] == self.cycle_ticks if p.mode == 'adjacent'
            else b['tick'] - a['tick'] > self.cycle_ticks) for a, b in zip(receipts, receipts[1:])),
            'actual feedback cadence, not the requested scheduling mode')
        # Two separately checked consumers bracket persistence: the first can
        # still forward, the second must retain the same version after service.
        # Both are real logical work, never a clock-count settling loop.
        await self.queries(p.histories, table=table, counter=p.counter(phase))
        await self.queries(tuple(reversed(p.histories)), table=table, counter=p.counter(phase))
        self.monitor.check()
        actual = self.monitor.memory()
        self.checker.persistent(owners, actual, phases=self.phases)
        protection = tuple(value.as_int() for value in self.monitor.protection.sample().counters)
        self.check(p.protection(phase), protection, 'all1024 protection cells retain declared logical effects')
        if table == 1:
            await self.queries(p.histories, table=0, counter=4)
        self.phases.append(dict(phase=phase, owners=owners, accepted=len(receipts),
            published=len(self.ledger.published), actual_services=len(self.ledger.services),
            actual_storage_sha256=sha256(json.dumps(sorted((str(k), v) for k,v in actual.items()),sort_keys=True).encode()).hexdigest()))

    async def run(self):
        self.monitor.start()
        c = self.coverage
        await self.learn('short', table=0, before_counter=None)
        c.reach('normally-learned-short-prerequisites')
        await self.learn('allocate', table=1, before_counter=None)
        await self.learn('reward', table=1, before_counter=4)
        c.reach('retired-versions-remain-consumable')
        await self.learn('reward-again', table=1, before_counter=5)
        for rule in ('unique-original-feedback-once', 'actual-feedback-cadence', 'complete-owned-version-writes',
                     'actual-persistent-service-and-storage-agree', 'fresh-reward-accumulates-after-turnover',
                     'all-protection-and-short-neighbors-preserved', 'all-final-learning-persists'):
            c.reach(rule)
        self.check(tuple(frozen for _, frozen in self.originals), tuple(source.meta for source, _ in self.originals),
                   'completed originals remain immutable after later learning and persistence')
        c.reach('completed-originals-immutable')
        self.agent.reference.raise_failure()
        c.finish()

    def evidence_value(self):
        return dict(program=self.program.state(), phases=self.phases, checks=self.checker.status_snapshot(),
            original_snapshots=len(self.originals), accepted_originals=len(self.ledger.feedback),
            published_versions=len(self.ledger.published), native_services=len(self.ledger.services),
            native_storage_checks=len(self.monitor.storage_checks),
            last_actual_services=self.monitor.attempts[-12:], last_memory_changes=self.monitor.memory_changes[-12:],
            native_memory_endpoint=[dict(table=table,index=index,entry=entry)
                for (table,index),entry in sorted(self.monitor.memory().items())],
            latest_native_shadow=self.monitor.latest_shadow,
            native_pending_state=_plain(self.monitor.ownership()),
            latest_published_versions=[dict(identity=row['version'].identity,counter=row['version'].counter,
                owner=row['version'].owner,phase=row['version'].phase,tick=row['tick'])
                for row in self.ledger.published[-self.program.count:]],
            monitor_failure=None if self.monitor.failure is None else repr(self.monitor.failure),
            semantic_failure=None if self.agent.reference.failure is None else str(self.agent.reference.failure),
            model_commits_are_not_hardware_service_evidence=True,
            actual_arrays_observed_read_only=True, arbitrary_settling_delays=False)


async def run(agent, program, coverage, evidence, *, environment_type=Environment):
    await agent.reset()
    env = environment_type(agent, program, coverage, evidence)
    try:
        await env.run()
        evidence.update(env.evidence_value(), status='PASS')
    except BaseException as error:
        evidence.update(env.evidence_value(), status='FAIL', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        # The first functional failure is reported once through the test body.
        # Retrieve monitor subscription tasks without converting it to teardown ERROR.
        await env.monitor.aclose(raise_failure=evidence.get('status') != 'FAIL')
