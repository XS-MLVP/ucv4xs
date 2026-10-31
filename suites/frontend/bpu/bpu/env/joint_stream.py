"""Queue complete old results; release only an actually observed conflict."""
from suites.frontend.bpu.bpu.env.joint_originals import Environment as OriginalEnvironment
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback


class Environment(OriginalEnvironment):
    async def feedback_originals(self,sources):
        c=self.checks
        c.begin_many(sources)
        await self.agent.set_ready(prediction=True,meta=True)
        transactions=[]
        for row in c.many:
            token=row['source'];outcome,=row['resolution'].branches
            tx=BpuBatchTraining(token.pc,row['receipt'].meta.resolve,(BpuBranchFeedback(
                outcome.position,outcome.target,int(outcome.kind),taken=int(outcome.taken),mispredict=int(outcome.mispredict)),))
            self.checker.plan_feedback(row['receipt'],tx)
            transactions.append(tx)
        transfers=tuple(self.agent.training_driver.send(tx) for tx in transactions)
        c.submitted(transfers)
        await self.observation.wait('two-old-results-wait-for-real-prediction-conflict',lambda _:bool(c.waiting))
        c.check((None,None),tuple(t.accepted_event for t in transfers),'neither pending old transfer has secretly completed')
        c.release_requested=self.checker.current_event.tick
        c.release_committed=await self.agent.set_ready(prediction=False,meta=True)
        accepted=tuple([await transfer for transfer in transfers])
        await self.pause()
        c.end_many(accepted)
        return accepted
