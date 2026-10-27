"""Genuine MainBTB programs and checkpoint recovery for shadow scenarios.

This helper owns public feedback and stopping/draining. It never writes a
shadow entry or constructs redirect metadata from a model/DUT state dump.
"""
from dataclasses import asdict

from bpuverify.bpu.case.abtb.timeouts import bounded
from bpuverify.bpu.model.sc.metadata import mbtb_counter_for_position, mbtb_meta_for_position
from bpuverify.bpu.transaction.types import BpuBatchTraining, BpuBranchFeedback, BpuRedirect


class ProgramEnvironment:
    def __init__(self, agent, checker, observation, report):
        self.agent, self.checker, self.observation = agent, checker, observation
        self.report, self.checkpoints = report, {}

    async def wait(self, operation, label, cycles=8192):
        return await bounded(self.agent, self.checker, operation, label, cycles)

    async def stop(self, label):
        await self.wait(self.agent.set_ready(prediction=False, meta=True), label + ': backpressure', 8)
        await self.wait(self.observation.drain(), label + ': accepted work retires', 32)
        self.checker.compare((None, None),
            (self.checker.counter.pending1, self.checker.counter.pending2),
            field='accepted_ABTB_tasks_drained', label=label)

    async def recover(self, target, checkpoint, label):
        self.checker.compare((target - 1) & ~7, checkpoint.prediction.start_pc & ~7,
            field='real_checkpoint_same_CFI_halfblock')
        self.checker.compare(True, checkpoint.prediction.start_pc <= target - 1,
            field='real_checkpoint_precedes_CFI')
        redirect = BpuRedirect(target, checkpoint.meta.redirect,
            cfi_pc=target - 1, taken=0, branch_type=1)
        boundary = await self.wait(self.agent.redirect(redirect), label + ': recovery', 32)
        self.report.setdefault('recoveries', []).append(dict(
            payload=redirect.payload(), source=asdict(checkpoint), accepted_tick=boundary))
        return await self.wait(self.agent.next_transaction(
            start_pc=target, after_tick=boundary, limit=256), label, 512)

    async def capture(self, program, label):
        return await self.recover(program['pc'], self.checkpoints[program['pc']], label)

    async def bootstrap(self, programs):
        pcs = sorted(program['pc'] for program in programs)
        # Cold fall-through visits 16-halfword-aligned starts. recover(pc - 1)
        # needs a genuine source in the SAME eight-halfword part as CFI pc-2.
        # Capture a real intermediate transaction for the second half instead
        # of requesting an aligned cold stream PC that it will never emit.
        leads = {pc: (pc - 2) & ~15 for pc in pcs}
        await self.wait(self.agent.reset(leads[pcs[0]]), 'reset before genuine cold checkpoints')
        cold_by_lead = {lead: await self.wait(self.agent.next_transaction(
            start_pc=lead, limit=512), 'aligned cold source', 2048) for lead in sorted(set(leads.values()))}
        cold = {pc: cold_by_lead[leads[pc]] for pc in pcs}
        await self.wait(self.agent.configure_predictors(ubtb=False, abtb=False, mbtb=True,
            tage=False, sc=False, ittage=False, ras=False, settle=True), 'MainBTB setup gate', 32)
        for pc in pcs:
            source = cold[pc]
            source_half = (pc - 2) & ~7
            if source_half != leads[pc]:
                source = await self.recover(source_half, source, 'genuine second-half cold checkpoint')
            self.checkpoints[pc] = await self.recover(pc - 1, source, 'nonaligned cold checkpoint')

    async def feedback(self, actual, branches):
        transaction = BpuBatchTraining(actual.prediction.start_pc, actual.meta.resolve, branches)
        self.checker.plan_feedback(transaction)
        await self.wait(self.agent.train_batch_with_prediction_pause(transaction), 'genuine MainBTB feedback', 256)
        self.report.setdefault('feedback', []).append(dict(
            phase=self.checker.phase, transaction=asdict(transaction)))

    @staticmethod
    def conditional(program, taken, mispredict):
        return BpuBranchFeedback(program['position'], program['pc'], 1,
            taken=taken, mispredict=mispredict)

    @staticmethod
    def fallback(program, mispredict=0):
        return BpuBranchFeedback(program['fallback'], program['pc'], 3,
            taken=1, mispredict=mispredict)

    async def prepare(self, program, label):
        self.checker.phase = label + '_prepare'
        await self.stop(label)
        await self.wait(self.agent.configure_predictors(abtb=False, settle=True), 'isolate MainBTB allocation', 32)
        await self.wait(self.agent.set_ready(prediction=True, meta=True), 'resume checkpoint capture', 8)
        actual = await self.capture(program, 'cold conditional')
        await self.feedback(actual, (self.conditional(program, 1, 1),))
        actual = await self.capture(program, 'allocated conditional')
        self.checker.compare(2, mbtb_counter_for_position(actual, program['position']),
            field='initial_conditional_counter')
        await self.feedback(actual, (self.conditional(program, 0, 1),))
        actual = await self.capture(program, 'negative conditional')
        self.checker.compare(1, mbtb_counter_for_position(actual, program['position']),
            field='negative_conditional_counter')
        await self.feedback(actual, (self.conditional(program, 0, 0), None, self.fallback(program, 1)))
        actual = await self.capture(program, 'two MainBTB residents')
        self.checker.compare((0, 3), (mbtb_counter_for_position(actual, program['position']),
            mbtb_meta_for_position(actual, program['fallback'])[1]['attribute']['branchType']),
            field='both_genuine_MainBTB_residents')

    async def steer(self, program, goal):
        await self.stop('direction change')
        await self.wait(self.agent.configure_predictors(abtb=False, settle=True), 'direction feedback gate', 32)
        await self.wait(self.agent.set_ready(prediction=True, meta=True), 'direction capture', 8)
        actual = await self.capture(program, 'real direction source')
        for _ in range(4):
            counter = mbtb_counter_for_position(actual, program['position'])
            if counter == goal:
                break
            taken = int(counter < goal)
            branch = self.conditional(program, taken, int((counter >= 2) != bool(taken)))
            await self.feedback(actual, (branch,) if taken else (branch, None, self.fallback(program)))
            actual = await self.capture(program, 'real direction transition')
            self.checker.compare(min(3, counter + 1) if taken else max(0, counter - 1),
                mbtb_counter_for_position(actual, program['position']), field='MainBTB_direction_transition')
        self.checker.compare(goal, mbtb_counter_for_position(actual, program['position']),
            field='MainBTB_direction_goal')
        await self.wait(self.agent.configure_predictors(abtb=True, settle=True), 'enable S3 fastTrain', 32)
        return await self.capture(program, 'natural loop start')

    async def steady_checkpoint(self, program, *, limit=128):
        """Qualify input history, never response/provider/slot output."""
        last = self.checker.records[-1]['tick']
        for _ in range(limit):
            actual = await self.wait(self.agent.next_transaction(
                start_pc=program['pc'], after_tick=last, limit=256), 'steady genuine checkpoint', 512)
            last = actual.prediction_tick
            if actual.meta.redirect['phr']['phrLowBits'] == program['conditional_history'] & 8191:
                # The checkpoint is S3 metadata. Its accepted S1 prediction
                # may legitimately be corrected by the trained MainBTB;
                # check the exact associated final S3, not the earlier S1.
                final = next(row['abtb']['final'] for row in self.checker.records
                             if row['tick'] == actual.meta_tick)
                self.checker.compare((1, program['pc'], program['pc'], 1, program['position'], 1),
                    tuple(final[name] for name in ('valid', 'pc', 'target', 'taken', 'position', 'branch_type')),
                    field='steady_checkpoint_is_installed_final_S3_conditional_self_loop')
                return actual
        raise AssertionError(dict(point='steady_input_history_not_reached', pc=program['pc'], limit=limit))

    async def restore_steady(self, program, checkpoint):
        """Restore the real installed CFI, not a fabricated preceding branch."""
        self.checker.compare(program['pc'], checkpoint.prediction.start_pc,
            field='steady_recovery_genuine_source_PC')
        redirect = BpuRedirect(program['pc'], checkpoint.meta.redirect,
            cfi_pc=(program['pc'] & ~7) + program['position'], taken=1, branch_type=1)
        boundary = await self.wait(self.agent.redirect(redirect), 'real self-loop recovery', 32)
        self.report.setdefault('steady_recoveries', []).append(dict(
            payload=redirect.payload(), source=asdict(checkpoint), accepted_tick=boundary))
        return boundary
