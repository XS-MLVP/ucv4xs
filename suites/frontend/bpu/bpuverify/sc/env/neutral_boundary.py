"""Existing SC agent owns driving, concurrent reads and complete monitoring."""
from bpuverify.sc.model.threshold import ScThresholdModel


class NeutralBoundaryEnv:
    def __init__(self, agent, program, checks, coverage):
        self.agent, self.program, self.checks, self.coverage = agent, program, checks, coverage
        self.thresholds = ScThresholdModel()
        self.frames = None
        self.last_cold_response = None

    async def consume(self, seeds, reverse=0, *, phase):
        p = self.program
        transfer = self.agent.submit_predict_branches(p.pc, p.layout)
        prediction = await transfer
        self.checks.prediction(p.expected(p.weight(seeds, reverse), p.thresholds(seeds, reverse)),
            prediction, state=dict(phase=phase, seeds=seeds, reverse=reverse))
        await self.agent.check_thresholds(p.thresholds(seeds, reverse))
        self.checks.check(True, transfer.accepted_event.tick > self.checks.feedback_records[-1]['tick'],
                          request='consumer is accepted after its actual feedback')
        return transfer, prediction

    async def guard(self, seeds, reverse=0):
        p = self.program
        prediction = await self.agent.predict_branches(p.pc + 16, p.layout)
        self.checks.prediction(p.expected(0, p.thresholds(seeds, reverse)), prediction,
                               state='independent untrained instruction window remains unchanged')

    async def send(self, source, kind, seeds, reverse=0):
        c, p = self.checks, self.program
        actual, intended = c.neutral_feedback(source) if kind == 'neutral' else c.feedback(source, reverse=kind == 'reverse')
        update = self.thresholds.apply(intended)
        c.check(p.prefix_slots if kind == 'neutral' else (p.prefix_slots[0],), update.qualifying_slots,
                request=dict(phase=kind, point='all intended original sources genuinely qualify'))
        c.check(p.thresholds(seeds, reverse), update.after, request='independent threshold vector follows the declared complete event')
        if kind == 'neutral':
            c.check(update.before, update.after, request='opposite qualified votes leave the full threshold vector unchanged')
            c.check(((0, 1, 0, 0), (0, 1, 0, 0)), (update.increments, update.decrements),
                    request='one positive and one negative threshold contribution')
        before = len(self.frames)
        await self.agent.train_batch(actual)
        c.accepted_feedback(source, kind, intended, self.frames[before:],
            branch_count=len(self.agent.ports.training.bits.branches),
            fold_count=len(self.agent.ports.training.bits.path_history), last_cold_response=self.last_cold_response)

    async def run(self):
        a, p, c, cov = self.agent, self.program, self.checks, self.coverage
        await a.reset()
        await a.check_thresholds(p.thresholds(0))
        cold_expected = p.expected(0, p.thresholds(0))
        pending = [a.submit_predict_branches(p.pc, p.layout) for _ in range(p.cold_source_count)]
        await a.drain_predictions()
        cold = [c.source(transfer, await transfer, cold_expected, state='distinct original before any learning') for transfer in pending]
        self.last_cold_response = max(c.sources[source]['completed'] for source in cold)
        c.mark(cov, 'distinct-originals', count=len(cold))
        c.mark(cov, 'shared-parameter-identity', positions=(1, 4), suffix=(8, 12))
        async with a.observe_feedback() as frames:
            self.frames = frames
            for step, source in enumerate(cold[:-1], 1):
                await self.send(source, 'seed', step)
                current = await self.consume(step, phase='qualified-boundary-history')
            c.mark(cov, 'qualified-boundary-history', accepted=p.seed_count, endpoint=p.endpoint, holds=2)
            await self.guard(p.seed_count)
            await self.send(cold[-1], 'neutral', p.seed_count)
            c.mark(cov, 'executed-prefix', resolved=((1, 0), (4, 1)), unexecuted=(8, 12))
            c.mark(cov, 'original-eligibility', slots=p.prefix_slots, current_confidence_not_used=True)
            current = await self.consume(p.seed_count, phase='neutral-consumer')
            c.mark(cov, 'neutral-feedback-retained', endpoint=p.endpoint)
            c.mark(cov, 'slot-placement-independent', placement=p.placement)
            for step in range(1, p.reverse_steps + 1):
                transfer, prediction = current
                expected = p.expected(p.weight(p.seed_count, step - 1), p.thresholds(p.seed_count, step - 1))
                source = c.source(transfer, prediction, expected, state=dict(phase='fresh reverse', step=step))
                await self.send(source, 'reverse', p.seed_count, step)
                current = await self.consume(p.seed_count, step, phase='exact-fresh-recovery')
                c.reverse_consumer(step, *current)
            c.mark(cov, 'fresh-reverse-learning', accepted=p.reverse_steps)
            c.mark(cov, 'exact-recovery-consumers', steps=p.crossing_steps, all_families=True)
            await self.guard(p.seed_count, p.reverse_steps)
            c.mark(cov, 'unrelated-experience-retained', suffix=(8, 12), independent_window=True)
