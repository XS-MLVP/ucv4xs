"""Existing asynchronous drivers, accepted-source proof and semantic consumers."""
from copy import deepcopy
from dataclasses import asdict, replace
from bpuverify.common.bundle.activity import bind_activity
from bpuverify.common.monitor.activity import ActivityMonitor
from bpuverify.ubtb.checker.semantic import prediction_value
from bpuverify.ubtb.checker.reset_lifetime import Checks, expected



class ResetLifetime:
    def __init__(self, agent, program, coverage, evidence):
        self.agent, self.program, self.coverage, self.evidence = agent, program, coverage, evidence
        self.checks = Checks(program)
        self.activity = ActivityMonitor(bind_activity(agent.dut, 'MicroBtb',
            {'learning': ('t1_fire_REG',)}, name='ubtb.reset-learning-activity'))
        self.phase, self.snapshots = 'prepare old execution', []
        self.evidence.update(sources=[], feedbacks=[])

    def check(self, wanted, actual, point):
        self.checks.check(wanted, actual, point, phase=self.phase)

    async def read(self, pc, branch=None):
        transfer = self.agent.submit_predict(pc)
        actual = await transfer
        self.agent.reference.raise_failure()
        wanted = dict(valid=0) if branch is None else prediction_value(expected(branch))
        self.check(wanted, prediction_value(actual), 'fresh complete response belongs to original request and lifetime')
        self.snapshots.append((actual, deepcopy(actual)))
        self.evidence['sources'].append(dict(pc=pc, accepted=transfer.accepted_event.tick,
            completed=transfer.completed_event.tick, value=prediction_value(actual)))
        return actual

    async def teach(self, branch):
        await self.agent.train(branch)
        self.evidence['feedbacks'].append(asdict(branch))

    async def old_learning(self):
        p, agent = self.program, self.agent
        if p.profile == 'committed':
            await self.activity.wait_idle()
            self.check(None, agent.reference.model.learning, 'committed control has no old pending learning')
            self.evidence['old_learning'] = None
            return
        # Both sources launch before either transfer is awaited; no gather or
        # scheduling mechanics leak into the testcase.
        fast = agent.training_driver.send(p.fast) if p.profile in ('fast-learning', 'competing-learning') else None
        resolved = agent.resolve_driver.send(p.resolve) if p.profile in ('resolve-learning', 'competing-learning') else None
        fast_event = None if fast is None else await fast
        resolve_event = None if resolved is None else await resolved
        if fast_event is not None and resolve_event is not None:
            self.check(fast_event.tick, resolve_event.tick, 'fastTrain and resolve actually accepted on one beat')
        activity = await self.activity.wait_active()
        agent.reference.raise_failure()
        self.check(True, agent.reference.model.learning is not None, 'actual learning is owned by an independent original')
        self.check(p.selected, agent.reference.model.learning.feedback, 'resolve priority selects original source before reset')
        self.evidence['old_learning'] = dict(selected=asdict(p.selected),
            fast_tick=None if fast_event is None else fast_event.tick,
            resolve_tick=None if resolve_event is None else resolve_event.tick,
            native_active_tick=activity.tick, native_active=activity.state)

    async def run(self):
        p, agent = self.program, self.agent
        await agent.reset()
        for branch in p.old:
            await self.teach(branch)
        for _ in range(2):
            await self.teach(replace(p.old[0], taken=0, mispredict=0))
        for branch in p.old:
            await self.read(branch.pc, branch)
        self.coverage.reach('distinct-old-residents', old=[asdict(b) for b in p.old])
        await self.old_learning()
        self.coverage.reach('old-learning-stage-proved', profile=p.profile)

        self.phase = 'reset old execution'
        await agent.reset()
        for pc in p.old_pcs:
            await self.read(pc)
        self.coverage.reach('post-reset-cold', old_pcs=p.old_pcs)
        await self.activity.wait_idle()
        for pc in reversed(p.old_pcs):
            await self.read(pc)
        self.coverage.reach('no-delayed-old-replay', old_pcs=p.old_pcs)

        self.phase = 'new execution has its own full reliability lifetime'
        for branch in p.new:
            await self.teach(branch)
            await self.read(branch.pc, branch)
        for errors in range(1, 4):
            await self.teach(replace(p.new[0], taken=0, mispredict=0))
            await self.read(p.new[0].pc, p.new[0] if errors < 3 else None)
            await self.read(p.new[1].pc, p.new[1])
        await self.teach(p.new[0])
        for branch in p.new:
            await self.read(branch.pc, branch)
        await self.read(p.fast.pc)
        await self.read(p.resolved.pc)
        self.coverage.reach('fresh-reliability-lifetime', errors_until_invalid=3, rebuilt=True)
        for original, frozen in self.snapshots:
            self.check(frozen, original, 'all original snapshots stay immutable across reset and relearning')
        self.coverage.reach('immutable-old-sources', snapshots=len(self.snapshots))
        agent.reference.raise_failure()
        self.coverage.finish()
        self.evidence.update(status='PASS', completed=sorted(self.coverage.completed),
            reference_checked=agent.reference.board.status.checked, reference_failed=agent.reference.board.status.failed)
