"""Public driver operations for adjacent real originals; no case-level IO."""
from suites.frontend.bpu.bpu.env.sc_loop_experience import Environment as LoopEnvironment
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback


class Environment(LoopEnvironment):
    async def capture_originals(self):
        c,p=self.checks,self.checks.program
        cold=await self.prepare()
        if p.trained:
            await self.controls(tage=False)
            await self.conditional(cold,True)
            await self.controls(tage=True)
            cold=await self.query_iteration(p.old_iteration)
            c.provider(cold)
        # One normal direction-only outcome strengthens the existing provider.
        # SC experience is preserved, and both results retain non-saturated six.
        await self.controls(sc=False)
        await self.conditional(cold,True)
        await self.controls(sc=True)
        c.expected_provider=6;c.phase='capture'
        first=await self.query_iteration(p.iterations[0])
        c.provider(first,p.iterations[0])
        await self.agent.set_ready(prediction=True,meta=True)
        second=await self.agent.next_transaction(start_pc=p.b,after_tick=first.prediction_tick)
        await self.pause()
        c.provider(second,p.iterations[1]);c.source(second,p.iterations[1])
        self.recent=second
        return first,second

    async def feedback_originals(self,sources):
        c=self.checks;c.begin_many(sources)
        transactions=[]
        for row in c.many:
            token=row['source'];outcome,=row['resolution'].branches
            tx=BpuBatchTraining(token.pc,row['receipt'].meta.resolve,(BpuBranchFeedback(
                outcome.position,outcome.target,int(outcome.kind),taken=int(outcome.taken),mispredict=int(outcome.mispredict)),))
            self.checker.plan_feedback(row['receipt'],tx);transactions.append(tx)
        transfers=tuple(self.agent.training_driver.send(tx) for tx in transactions)
        c.check((None,None),tuple(tx.accepted_event for tx in transfers),'both transfers are submitted before yielding to acceptance')
        c.mark('submissions-before-await')
        accepted=tuple([await transfer for transfer in transfers])
        await self.pause();c.end_many(accepted)
        return accepted
