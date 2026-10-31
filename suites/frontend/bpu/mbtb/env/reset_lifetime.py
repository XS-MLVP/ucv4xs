"""Normal agent drives; protocol-stage evidence and reset are hidden here."""
from copy import deepcopy
from dataclasses import asdict, replace

from suites.frontend.bpu.mbtb.bundle.values import _plain
from suites.frontend.bpu.mbtb.env.full_capacity_learning import planned_payload, observed_payload
from suites.frontend.bpu.mbtb.transaction.types import MbtbBatchTraining, MbtbBranchFeedback
from suites.frontend.bpu.mbtb.checker.reset_lifetime import Checks


class ResetLifetime:
    def __init__(self, agent, program, coverage, evidence):
        self.agent, self.program, self.coverage, self.evidence = agent, program, coverage, evidence
        self.checks = Checks(program)
        self.snapshots = []

    async def predict(self, pc):
        transfer = self.agent.submit_predict(pc)
        result = await transfer
        self.agent.reference.raise_failure()
        self.snapshots.append((result, deepcopy(result)))
        return transfer, result

    def transaction(self, branch, source, *, taken=1, allocate=True):
        return MbtbBatchTraining(branch.pc, deepcopy(source.meta_entries), (
            MbtbBranchFeedback(branch.target, taken, branch.position, branch.kind, 0, int(allocate)),))

    async def teach(self, branch, *, taken=1, allocate=True):
        _, source = await self.predict(branch.pc)
        await self.agent.train_batch(self.transaction(branch, source, taken=taken, allocate=allocate))

    def activity(self):
        state = _plain(self.agent.training_activity.binding.bits.sample())
        return {group: tuple(values) for group, values in state.items()}

    async def run(self):
        check, program = self.checks, self.program
        await self.agent.reset()
        for branch in program.old:
            await self.teach(branch)
        for _ in range(2):
            await self.teach(program.old[0], taken=0, allocate=False)
        for branch in program.old:
            _, result = await self.predict(branch.pc)
            check.resident(result, branch, counter=0 if branch.kind == 1 else None)
        self.coverage.reach('distinct-old-residents', old=[asdict(b) for b in program.old])

        pending = (program.old[0] if program.profile == 'registered-direction' else
                   replace(program.old[1], target=0x400089ac) if program.profile == 'registered-retarget'
                   else program.pending)
        _, original = await self.predict(pending.pc)
        if program.profile not in ('registered-direction', 'registered-retarget'):
            check.cold(original)
        receipt_floor = self.agent.reference.accepted_feedback[-1][0]
        if program.profile != 'committed':
            transaction = self.transaction(pending, original, allocate=program.profile != 'registered-direction')
            # Existing PulseDriver owns rise-write launch and deassertion. Do
            # not use train_batch here: its contract drains the old lifetime.
            await self.agent.training_driver.send(self.agent._encode_training(transaction))
            check.phase = 'actual old feedback before reset'
            stage = self.activity()
            check.check(True, any(stage['writes']),
                        'real native write obligation, not merely an offered transaction')
            receipts = [(tick, observed_payload(feedback))
                        for tick, feedback in self.agent.reference.accepted_feedback if tick > receipt_floor]
            check.check(1, len(receipts), 'exactly one actual old feedback receipt')
            check.check(planned_payload(transaction), receipts[0][1], 'receipt retains complete original metadata')
            self.evidence['old_feedback'] = dict(accepted_tick=receipts[0][0], payload=receipts[0][1])
            state = self.agent.reference.model.state()
            self.evidence['independent_old_obligations'] = dict(
                pending_entries=sum(state['entry_pending'].values()),
                pending_directions=sum(state['counter_pending'].values()),
                offered=state['offered'] is not None, populated_cells=state['populated_cells'])
        else:
            stage = self.activity()
            check.check(False, any(value for group in stage.values() for value in group),
                        'resident control has no pending old learning')
        self.evidence['pre_reset_activity'] = stage
        self.coverage.reach('old-learning-stage-proved', profile=program.profile, activity=stage)

        check.phase = 'reset old instruction lifetime'
        waited = await self.agent.reset()
        self.agent.reference.raise_failure()
        self.evidence['reset_wait_samples'] = waited
        check.check(False, any(value for group in self.activity().values() for value in group),
                    'initialization completes without pending old writes')
        for pc in program.old_pcs:
            _, result = await self.predict(pc)
            check.cold(result)
        self.coverage.reach('post-reset-cold', old_pcs=program.old_pcs)
        await self.agent.training_activity.wait_idle()
        for pc in reversed(program.old_pcs):
            _, result = await self.predict(pc)
            check.cold(result)
        self.coverage.reach('no-delayed-old-replay', old_pcs=program.old_pcs)

        check.phase = 'new sources own new learning'
        for branch in program.new:
            await self.teach(branch)
        for branch in program.new:
            _, result = await self.predict(branch.pc)
            check.resident(result, branch, counter=2 if branch.kind == 1 else None)
            check.check(1, sum(e.valid for e in result.entries), 'old same-window sibling does not resurrect')
        await self.teach(program.new[0], taken=0, allocate=False)
        for branch in program.new:
            _, result = await self.predict(branch.pc)
            check.resident(result, branch, counter=1 if branch.kind == 1 else None)
        _, result = await self.predict(program.pending.pc)
        check.cold(result)
        self.coverage.reach('new-owned-learning', new=[asdict(b) for b in program.new])
        for original, frozen in self.snapshots:
            check.check(frozen, original, 'old and new prediction snapshots remain immutable')
        self.coverage.reach('immutable-old-sources', snapshots=len(self.snapshots))
        self.agent.reference.raise_failure()
        self.coverage.finish()
        self.evidence.update(status='PASS', completed=sorted(self.coverage.completed),
            reference_checked=self.agent.reference.board.status.checked,
            reference_failed=self.agent.reference.board.status.failed)
