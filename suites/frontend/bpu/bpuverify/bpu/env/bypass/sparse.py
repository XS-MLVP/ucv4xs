"""Public-feedback construction and real D -> A recovery for sparse rings."""
from dataclasses import asdict

from bpuverify.bpu.env.bypass.program import ProgramEnvironment
from bpuverify.bpu.transaction.types import BpuBranchFeedback, BpuRedirect


class SparseProgramEnvironment(ProgramEnvironment):
    async def install_return(self, pc, target, label):
        """Allocate or retarget a real unconditional edge using captured metadata."""
        await self.stop(label)
        await self.wait(self.agent.configure_predictors(abtb=False, settle=True), label + ': feedback gate', 32)
        await self.wait(self.agent.set_ready(prediction=True, meta=True), label + ': capture', 8)
        actual = await self.capture(dict(pc=pc), label + ': genuine source')
        await self.feedback(actual, (BpuBranchFeedback(7, target, 3, taken=1, mispredict=1),))
        actual = await self.capture(dict(pc=pc), label + ': installed readback')
        self.check_final(actual, pc=pc, target=target, position=7, branch_type=3,
            field='genuine_installed_' + label)
        return actual

    def use_steady_source(self, program, checkpoint, *, source='D'):
        """Opt into a real D -> A or C -> D source for direction captures.

        Cold captures still use the ordinary preceding-CFI source. A warm
        scenario can preserve program ancestry instead of repeatedly flushing
        its history to that cold source while changing MainBTB direction.
        """
        if source not in ('C', 'D'):
            raise ValueError('warm sparse source must be C or D')
        slot = 2 if source == 'C' else 3
        target = program['nodes'][3] if source == 'C' else program['pc']
        self.checker.compare(program['nodes'][slot], checkpoint.prediction.start_pc,
            field='warm_direction_source_is_genuine_' + source)
        self.check_final(checkpoint, pc=program['nodes'][slot], target=target, position=7, branch_type=3,
            field='warm_direction_source_has_installed_edge')
        if not hasattr(self, '_steady_sources'):
            self._steady_sources = {}
        self._steady_sources[program['pc']] = (checkpoint, source)

    async def capture(self, program, label):
        entry = getattr(self, '_steady_sources', {}).get(program['pc'])
        if entry is None:
            return await super().capture(program, label)
        checkpoint, source = entry
        if source == 'D':
            boundary = await self.restore_steady(program, checkpoint)
        else:
            # Start at D: its first normal D -> A request retains the older
            # C -> D index ancestor instead of seeding an A-index redirect.
            redirect = BpuRedirect(program['nodes'][3], checkpoint.meta.redirect,
                cfi_pc=(program['nodes'][2] & ~7) + 7, taken=1, branch_type=3)
            boundary = await self.wait(self.agent.redirect(redirect), 'real sparse C-to-D recovery', 32)
            self.report.setdefault('steady_recoveries', []).append(dict(
                payload=redirect.payload(), source=asdict(checkpoint), accepted_tick=boundary))
        return await self.wait(self.agent.next_transaction(start_pc=program['pc'], after_tick=boundary, limit=256),
            label + ': real warm source', 512)

    async def align_upper_boundary(self, target_slot, until, *, attempts=8):
        """Align AFTER draining; keep natural history flow between stops.

        Already accepted work may advance enq after backpressure is requested.
        Measure that retirement in the reset-derived model, then move the next
        stopping boundary earlier by that many writes. Never inspect chosen or
        response data, or repeatedly stop on the first transient A request.
        """
        upper = self.checker.bypass.references[1]
        stop_slot = target_slot
        for _ in range(attempts):
            if upper.enq % 8 == target_slot:
                return
            await self.wait(self.agent.set_ready(prediction=True, meta=True),
                            'natural sparse flow for wrap boundary', 8)
            await until(lambda: upper.enq % 8 == stop_slot, 'model upper enqueue stopping boundary')
            before = upper.enq
            await self.stop('retire accepted work at sparse wrap boundary')
            retired = (upper.enq - before) % 16
            self.report.setdefault('boundary_alignment', []).append(dict(
                target_slot=target_slot, stop_slot=stop_slot, before_enq=before,
                after_enq=upper.enq, accepted_writes_retired=retired,
                tick=self.checker.bypass.last_event.tick))
            stop_slot = (target_slot - retired) % 8
        self.checker.compare(target_slot, upper.enq % 8,
                             field='sparse_wrap_boundary_reached_after_accepted_work', attempts=attempts)

    @staticmethod
    def conditional(program, taken, mispredict):
        return BpuBranchFeedback(program['position'], program['target'], 1,
                                 taken=taken, mispredict=mispredict)

    @staticmethod
    def fallback(program, mispredict=0):
        return BpuBranchFeedback(program['fallback'], program['target'], 3,
                                 taken=1, mispredict=mispredict)

    async def prepare_returns(self, program, label):
        await self.stop(label + ': return allocation')
        await self.wait(self.agent.configure_predictors(abtb=False, settle=True), 'return allocation gate', 32)
        await self.wait(self.agent.set_ready(prediction=True, meta=True), 'return checkpoints', 8)
        nodes = program['nodes']
        for source, target in zip(nodes[1:], nodes[2:] + nodes[:1], strict=True):
            actual = await self.capture(dict(pc=source), 'genuine cold return source')
            await self.feedback(actual, (BpuBranchFeedback(7, target, 3, taken=1, mispredict=1),))
            actual = await self.capture(dict(pc=source), 'installed return readback')
            self.check_final(actual, pc=source, target=target, position=7, branch_type=3,
                             field='genuine_installed_return')

    def check_final(self, actual, *, pc, target, position, branch_type, field):
        final = next(row['abtb']['final'] for row in self.checker.records if row['tick'] == actual.meta_tick)
        self.checker.compare((1, pc, target, 1, position, branch_type),
            tuple(final[name] for name in ('valid', 'pc', 'target', 'taken', 'position', 'branch_type')),
            field=field)

    async def steady_checkpoint(self, program, *, taken=True, limit=128, source='D'):
        """Save a real installed C -> D or D -> A checkpoint."""
        if source not in ('C', 'D'):
            raise ValueError('steady sparse source must be C or D')
        pc = program['nodes'][2 if source == 'C' else 3]
        target = program['nodes'][3] if source == 'C' else program['pc']
        context = program['positive' if taken else 'negative'][pc]
        last = self.checker.records[-1]['tick']
        for _ in range(limit):
            actual = await self.wait(self.agent.next_transaction(start_pc=pc, after_tick=last, limit=256),
                                     'sparse steady D checkpoint', 512)
            last = actual.prediction_tick
            if actual.meta.redirect['phr']['phrLowBits'] == context['history'] & 8191:
                self.check_final(actual, pc=pc, target=target, position=7, branch_type=3,
                                 field='steady_checkpoint_is_genuine_' + source)
                return actual
        raise AssertionError(dict(point='sparse_input_history_not_reached', pc=pc, limit=limit))

    async def restore_steady(self, program, checkpoint):
        self.checker.compare(program['nodes'][3], checkpoint.prediction.start_pc,
                             field='sparse_recovery_genuine_D_source_PC')
        self.check_final(checkpoint, pc=program['nodes'][3], target=program['pc'], position=7, branch_type=3,
                         field='sparse_recovery_source_is_installed_return')
        redirect = BpuRedirect(program['pc'], checkpoint.meta.redirect,
            cfi_pc=(program['nodes'][3] & ~7) + 7, taken=1, branch_type=3)
        boundary = await self.wait(self.agent.redirect(redirect), 'real sparse D-to-A recovery', 32)
        self.report.setdefault('steady_recoveries', []).append(dict(
            payload=redirect.payload(), source=asdict(checkpoint), accepted_tick=boundary))
        return boundary
