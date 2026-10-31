"""Real conditional-loop episodes and public driver feedback completion."""
from suites.frontend.bpu.bpu.env.statistical_prefix import Program as PrefixProgram
from suites.frontend.bpu.bpu.driver.recovery import RecoveryDriver
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback


class Environment(PrefixProgram):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.recent=None

    async def conditional(self,receipt,taken,*,maximum=False):
        token=self.checks.save(receipt)
        late=self.checks.bank.statistical_snapshot(token,resolved=True).late
        return await self.feedback(receipt,self.checks.program.outcome(token,late,taken),maximum=maximum)

    async def query_iteration(self,count):
        p,c=self.checks.program,self.checks
        if self.recent is None:
            self.anchor=await PrefixProgram.query(self,p.a)
        else:
            # The conditional is not taken on this exit occurrence, then its
            # following real jump returns to the entry. Recover the recent
            # original, not an entry checkpoint overwritten by the loop.
            await self.pause()
            boundary=await RecoveryDriver(self.agent,self.checker).send(self.recent,
                position=p.exit_position,branch_type=int(Kind.INDIRECT),target=p.a)
            self.anchor=await self.agent.next_transaction(start_pc=p.a,after_tick=boundary)
            c.save(self.anchor)
            await self.pause()
        source=await PrefixProgram.query(self,p.b)
        await self.agent.set_ready(prediction=True,meta=True)
        while True:
            token=c.save(source)
            iteration=c.bank.queries.snapshot(token).loop
            if iteration>=count:
                c.check(count,iteration,'the exact declared loop iteration must not be skipped')
                await self.pause()
                self.recent=source
                return source
            source=await self.agent.next_transaction(start_pc=p.b,after_tick=source.prediction_tick)

    async def prepare(self):
        c,p=self.checks,self.checks.program
        await self.controls(ubtb=True,abtb=False,ittage=False,tage=False,sc=False)
        # Normal taken outcomes establish a natural self-loop. A genuine NT
        # outcome allocates a negative TAGE provider; subsequent true outcomes
        # strengthen that same real provider without fabricating mispredicts.
        for _ in range(2):
            await self.conditional(await self.query_iteration(0),True)
        await self.controls(tage=True)
        await self.conditional(await self.query_iteration(p.old_iteration),False,maximum=True)
        for _ in range(2):
            await self.conditional(await self.query_iteration(p.old_iteration),True)
        await self.controls(sc=True)
        cold=await self.query_iteration(p.old_iteration)
        slot,value=c.provider(cold)
        c.check(0,value.prediction.used[slot],'cold loop experience cannot claim SC authority')
        c.cold_read=value.original.read
        c.mark('valid-nonzero-original')
        c.mark('owned-five-family-read')
        c.mark('cold-unused-control')
        return cold

    async def feedback_original(self,source,taken,label):
        c,p=self.checks,self.checks.program
        token=c.save(source)
        value=c.bank.statistical_snapshot(token,resolved=True)
        outcome=p.outcome(token,value.late,taken)
        c.begin(source,taken,label)
        transaction=BpuBatchTraining(token.pc,source.meta.resolve,(BpuBranchFeedback(
            outcome.position,outcome.target,int(outcome.kind),taken=int(outcome.taken),
            mispredict=int(outcome.mispredict)),))
        self.checker.plan_feedback(source,transaction)
        transfer=self.agent.training_driver.send(transaction)
        if c.probe['concurrent'] and c.probe['needs_read']:
            await self.observation.wait('old-loop-feedback-actually-blocked',lambda _:bool(c.probe['blocked']))
            c.check(None,transfer.accepted_event,'old read conflict has not accepted the held proposal')
            await self.agent.set_ready(prediction=False,meta=True)
        accepted=await transfer
        await self.pause()
        c.end(accepted.tick)

    async def warm(self):
        c,p=self.checks,self.checks.program
        c.warm_sources=tuple([await self.query_iteration(p.old_iteration) for _ in range(p.teaching_count)])
        await self.controls(tage=False)
        for index,source in enumerate(c.warm_sources):
            await self.feedback_original(source,True,f'cold-{index}')
        await self.controls(tage=True)
        source=await self.query_iteration(p.old_iteration)
        slot,value=c.provider(source)
        c.check((1,1,1),(value.prediction.used[slot],value.prediction.directions[slot],value.prediction.above[slot]),
            'genuine nonzero-iteration experience earns strong SC authority')
        c.check(True,all(a!=b for a,b in zip(c.cold_read.weights,value.original.read.weights,strict=True)),
            'fresh loop consumer reads changed learning in every family')
        c.consume(source,p.old_iteration,'strong')
        c.mark('strong-loop-consumer')
        return source

    async def younger(self,source,*,learn_tage=False):
        c,p=self.checks,self.checks.program
        await self.controls(tage=learn_tage)
        await self.agent.set_ready(prediction=True,meta=True)
        current=source
        while True:
            current=await self.agent.next_transaction(start_pc=p.b,after_tick=current.prediction_tick)
            token=c.save(current)
            iteration=c.bank.queries.snapshot(token).loop
            if iteration>=p.young_iteration:
                c.check(p.young_iteration,iteration,'declared younger iteration must actually be consumed')
                c.source(current,iteration)
                if not p.overlap:await self.pause()
                self.recent=current
                return current
