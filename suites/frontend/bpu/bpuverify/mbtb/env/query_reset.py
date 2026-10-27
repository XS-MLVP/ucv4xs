"""Normal drivers own waveform timing; source dispositions stay in the monitor."""
from copy import deepcopy
from bpuverify.common.env.wait import wait_condition
from bpuverify.mbtb.transaction.types import MbtbLookup, MbtbBatchTraining, MbtbBranchFeedback
from bpuverify.mbtb.checker.query_reset import Checks
from bpuverify.mbtb.monitor.query_reset import QueryMonitor

class QueryResetLifetime:

    def __init__(self, agent, program, coverage, evidence):
        self.agent, self.program, self.coverage, self.evidence = (agent, program, coverage, evidence)
        self.checks = Checks(program)
        self.snapshots = []

    async def read(self, pc, branches):
        transfer = self.agent.submit_predict(pc)
        actual = await transfer
        self.agent.reference.raise_failure()
        self.checks.prediction(actual, pc, branches)
        self.snapshots.append((actual, deepcopy(actual)))
        return actual

    async def teach(self, branch):
        source = await self.agent.predict(branch.pc)
        self.snapshots.append((source, deepcopy(source)))
        await self.agent.train_batch(MbtbBatchTraining(branch.pc, deepcopy(source.meta_entries), (MbtbBranchFeedback(branch.target, 1, branch.position, branch.kind, branch.action, 1),)))

    async def run(self):
        agent, p, check = (self.agent, self.program, self.checks)
        await agent.reset()
        for branch in p.old:
            await self.teach(branch)
        for pc in dict.fromkeys((b.pc for b in p.old)):
            await self.read(pc, p.old)
        await self.read(p.old[0].pc, p.old)
        self.coverage.reach('warm-originals')
        response_status = agent.prediction_scoreboard.status
        monitor = QueryMonitor(agent, p, check).start()
        try:
            request = MbtbLookup(p.old[0].pc)
            launch = await agent.lookup_driver.send(request)
            if p.mode == 'response-before-reset':
                await wait_condition(agent.dut.clock, sample=monitor.status, satisfied=lambda state: state['disposition'] is not None, name='mbtb' + '.old-query-response', timeout_cycles=64)
            await agent.reset()
            state = monitor.status()
            fields = ('submitted', 'accepted', 'completed', 'cancelled', 'pending', 'processing')
            before = {name: getattr(response_status, name) for name in fields}
            after = {name: getattr(agent.prediction_scoreboard.status, name) for name in fields}
            check.check(before, after, 'acceptance-only old query does not fake a response-handle completion')
            check.check(True, state['accepted_tick'] > launch.tick, 'actual lookup follows input launch')
            check.check(p.disposition, state['disposition'], 'source-qualified response/reset relation')
            check.check(True, state['reset_tick'] > state['accepted_tick'], 'effective reset follows actual old admission')
            if p.disposition == 'responded':
                check.check(True, state['accepted_tick'] <= state['response_tick'] < state['reset_tick'], 'complete old response precedes reset')
                self.snapshots.append((monitor.actual_response, deepcopy(monitor.actual_response)))
            else:
                check.check(None, state['response_tick'], 'no old response before reset-ended obligation')
            check.check(True, monitor.previous_same_pc_is_not_this_request, 'same-PC previous response cannot satisfy new source obligation')
            self.coverage.reach('actual-old-query', launch_tick=launch.tick, accepted_tick=state['accepted_tick'])
            self.coverage.reach('old-response-disposition', **state)
            old_snapshot = monitor.lease.snapshot
            frozen_snapshot = monitor.snapshot_frozen
            self.evidence['old_query'] = dict(launch_tick=launch.tick, **state, ignored_previous_same_pc_frame=monitor.previous_same_pc_is_not_this_request, complete_old_payload_checked=monitor.actual_response is not None, response_handle_counts_before=before, response_handle_counts_after=after)
        finally:
            await monitor.aclose()
        check.phase = 'new reset epoch'
        for pc in dict.fromkeys((b.pc for b in p.old)):
            await self.read(pc, ())
        self.coverage.reach('new-epoch-cold')
        for branch in p.new:
            await self.teach(branch)
        for pc in dict.fromkeys((b.pc for b in p.new)):
            await self.read(pc, p.new)
        self.coverage.reach('new-owned-learning')
        check.check(frozen_snapshot, old_snapshot, 'old logical request snapshot survives reset and new learning unchanged')
        for original, frozen in self.snapshots:
            check.check(frozen, original, 'all old and new actual response snapshots remain immutable')
        self.coverage.reach('immutable-originals', snapshots=len(self.snapshots))
        agent.reference.raise_failure()
        self.coverage.finish()
        self.evidence.update(status='PASS', completed=sorted(self.coverage.completed), reference_checked=agent.reference.board.status.checked, reference_failed=agent.reference.board.status.failed)
