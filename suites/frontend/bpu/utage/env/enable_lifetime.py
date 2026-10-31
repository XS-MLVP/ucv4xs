"""Normal drivers and semantic witnesses; no testcase edges or direct writes."""
import asyncio
from contextlib import suppress
from copy import deepcopy

from toffee import AnyOf, SimTimeout, TaskComplete, XEventKind
from suites.frontend.bpu.utage.env.usefulness_events import usefulness_env
from suites.frontend.bpu.utage.checker.enable_lifetime import EnableLifetimeChecks
from suites.frontend.bpu.utage.checker.checking import UtageUsefulChecker
from suites.frontend.bpu.utage.transaction.types import UtageTraining
from suites.frontend.bpu.utage.model.enable_lifetime import PC, POSITION, HISTORY, NEIGHBOR_HISTORY
from suites.frontend.bpu.utage.monitor.enable_lifetime import LearningBoundaryMonitor


class EnableLifetime:
    def __init__(self, agent, program, coverage, evidence):
        self.agent, self.program, self.coverage, self.evidence = agent, program, coverage, evidence
        self.checks = EnableLifetimeChecks(agent.reference, program)
        self.sources = []

    async def source(self, history, expected):
        source = await self.agent.predict(PC, POSITION, 1 - expected.taken, folded_history=history)
        slot = source.meta['abtbResult'][0]
        self.checks.check((1, self.program.table, expected.counter, expected.taken),
            (source.hit, slot['tableId'], slot['takenCtr_value'], source.taken),
            'fresh owned provider, full confidence and learned direction')
        self.sources.append((source, deepcopy(source.meta)))
        return source

    async def wait_trigger(self, monitor):
        async def wait(): return await monitor.trigger
        task = asyncio.create_task(wait())
        try:
            event = await AnyOf(TaskComplete(task), SimTimeout(64, clock=self.agent.dut.clock))
            if event.kind is XEventKind.TIMEOUT:
                raise TimeoutError('declared UTAGE learning boundary was not observed')
            self.agent.reference.raise_failure()
            return event.value
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError): await task

    async def run(self):
        agent, p, coverage = self.agent, self.program, self.coverage
        # The old all-enabled preparation checker has its own scope. Close it
        # before disable; the always-on semantic checker remains independent.
        async with usefulness_env(agent, p.seed, None) as preparation:
            await preparation.seed(NEIGHBOR_HISTORY)
            await preparation.seed(HISTORY)
        original = await self.source(HISTORY, p.initial)
        coverage.reached('warm-owned-sources')
        accepted_before = agent.reference.model.accepted_feedback
        monitor = LearningBoundaryMonitor(agent).start()
        task = None
        try:
            self.checks.check(p.protection(p.initial), monitor.all_protection(), 'all protection from declared reset-derived preparation')
            monitor.arm(p.phase)
            tx = UtageTraining(PC, POSITION, p.initial.taken, original.meta, mispredict=0)
            task = asyncio.create_task(agent.training_driver.send(agent.compact_training(tx)))
            trigger = await self.wait_trigger(monitor)
            await agent.set_enabled(False)
            await task
            await agent.training_activity.wait_idle('pipeline')
            agent.reference.raise_failure()
            raw = [row for row in monitor.rows if row['public']['valid']]
            self.checks.check(1, len(raw), 'one actual original raw feedback, no replay pulse')
            self.checks.check(UtageUsefulChecker._payload(tx), raw[0]['public']['bits'], 'complete original input payload')
            coverage.reached('one-complete-original-feedback', accepted_tick=raw[0]['tick'])
            self.checks.check(int(p.qualifies), agent.reference.model.accepted_feedback - accepted_before,
                       'current enable qualifies the registered original once, or rejects it permanently')
            coverage.reached('declared-qualification-lifetime', trigger_tick=trigger['tick'], qualifies=p.qualifies)
            self.checks.check(p.protection(p.disabled), monitor.all_protection(), 'complete actual protection while disabled')
            if p.qualifies:
                changed = [row for row in monitor.rows if row['changes'] and not row['enabled']]
                self.checks.check(True, bool(changed), 'already qualified protection becomes visible while disabled')
            else:
                self.checks.check(False, any(row['changes'] for row in monitor.rows), 'rejected feedback has no hidden protection effect')
            coverage.reached('disabled-visible-effect')
            coverage.reached('all-other-protection-preserved')
            await agent.set_enabled(True)
            fresh = await self.source(HISTORY, p.disabled)
            await self.source(NEIGHBOR_HISTORY, p.initial)
            self.checks.check(int(p.qualifies), agent.reference.model.accepted_feedback - accepted_before,
                       'reopening does not resurrect or duplicate an old feedback')
            self.checks.check(p.protection(p.disabled), monitor.all_protection(), 'reopened exact state without relearning')
            coverage.reached('reopened-without-replay')
            await agent.train(UtageTraining(PC, POSITION, p.disabled.taken, fresh.meta, mispredict=0))
            await self.source(HISTORY, p.reopened_learning)
            await self.source(NEIGHBOR_HISTORY, p.initial)
            self.checks.check(p.protection(p.reopened_learning), monitor.all_protection(), 'new feedback can learn after reopening')
            self.checks.check(1 + int(p.qualifies), agent.reference.model.accepted_feedback - accepted_before,
                       'only the declared new qualification is added')
            coverage.reached('fresh-learning-after-reopen')
            self.checks.check(True, all(source.meta == frozen for source, frozen in self.sources), 'all original metadata immutable')
            coverage.reached('immutable-originals')
            self.evidence.update(status='PASS', program=p.state(), trigger=trigger,
                actual_raw_feedback=raw, actual_qualified_delta=agent.reference.model.accepted_feedback - accepted_before,
                disabled_changes=[dict(tick=row['tick'], changes=row['changes']) for row in monitor.rows if not row['enabled'] and row['changes']],
                original_sources=len(self.sources), immutable_originals=True)
        finally:
            if task is not None:
                if not task.done(): task.cancel()
                with suppress(asyncio.CancelledError): await task
            await monitor.aclose()
        agent.reference.raise_failure()
        coverage.finish()
